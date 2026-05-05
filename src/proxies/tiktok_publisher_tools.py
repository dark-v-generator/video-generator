"""Custom browser-use tools for the TikTok publisher agent.

We deliberately keep the surface tiny:

* ``run_js(code)``                — execute arbitrary JS, return the value
* ``click_by_text(text, role?)``  — find a visible element by its text and click
* ``set_contenteditable(selector, text)`` — properly clear+type a DraftJS
                                            (or other rich-text) field
* ``get_text(selector)``          — read the visible text of an element

The philosophy is "few sharp tools, big toolbox via JS" rather than a
zoo of pre-defined high-level actions. The agent reaches for ``run_js``
when the standard browser-use actions can't do the job — e.g. clearing
DraftJS contenteditable, reading internal state, finding elements by
fuzzy text matching that the DOM dump indices don't expose.

The other three (``click_by_text`` / ``set_contenteditable`` /
``get_text``) are convenience wrappers that bake reliable JS snippets
into named actions so the agent doesn't have to retype them every run.

All four actions are best-effort: on JS error we return a structured
error string in ``ActionResult.extracted_content`` so the agent can
read it, retry differently, or call ``done(success=False)``.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional

from browser_use import ActionResult
from browser_use.tools.service import Tools
from pydantic import BaseModel, Field

from src.core.logging_config import get_logger

_logger = get_logger(__name__)


def _wrap_js_for_eval(code: str) -> str:
    """Make user-supplied JS legal as a CDP ``Runtime.evaluate`` expression.

    CDP evaluates the input as an EXPRESSION, so a top-level ``return``
    is a SyntaxError. The agent (correctly, intuitively) writes things
    like ``return document.title`` because that's what every JS console
    accepts. We auto-wrap such snippets in an IIFE so both styles work:

    * ``return X``                   -> wrapped in ``(() => { ... })()``
    * ``X``  (bare expression)       -> passed through unchanged
    * ``(() => ...)()``  (already IIFE) -> passed through unchanged
    * ``async () => await X``        -> passed through (caller adds ``()``)
    """
    stripped = code.strip()
    if not stripped:
        return code
    # Already an IIFE call, an arrow function, or a parenthesized expression.
    if stripped.startswith("("):
        return code
    # Top-level return statement => wrap in an IIFE so the bare return
    # is legal. We use a non-async arrow; await usage inside still works
    # because awaitPromise=True on Runtime.evaluate handles top-level
    # promises returned from the IIFE.
    if re.search(r"^\s*return\b|\n\s*return\b", code):
        return f"(() => {{ {code} }})()"
    # Multi-statement code without an explicit return. Wrap so it's at
    # least syntactically valid; result will be undefined unless the
    # last expression is naturally returned (which JS doesn't do here).
    if ";" in stripped.rstrip(";") or "\n" in stripped:
        return f"(() => {{ {code} }})()"
    return code


# ---------------------------------------------------------------------------
# Pydantic param models — these define the JSON shape the LLM must produce.
# ---------------------------------------------------------------------------


class RunJSAction(BaseModel):
    """Run a JavaScript snippet in the active tab."""

    code: str = Field(
        description=(
            "JavaScript to evaluate in the active tab. The snippet is run "
            "with Runtime.evaluate (returnByValue=true, awaitPromise=true). "
            "Use `return <expr>` for non-trivial values; bare expressions "
            "also work. Wrap in an IIFE for multi-statement code: "
            "`(() => { const x = ...; return x; })()`. "
            "On exception, the error message is returned to you as text."
        )
    )


class ClickByTextAction(BaseModel):
    """Click the first visible element whose innerText matches."""

    text: str = Field(
        description=(
            "Visible text to match (case-insensitive substring). The first "
            "element that contains this text and is currently visible is "
            "clicked via JS .click()."
        )
    )
    role: Optional[str] = Field(
        default=None,
        description=(
            "Optional ARIA role to narrow the search (e.g. 'button', "
            "'tab', 'link', 'menuitem'). If omitted, any element matches."
        ),
    )


class SetContenteditableAction(BaseModel):
    """Clear and re-fill a contenteditable element (DraftJS-friendly)."""

    selector: str = Field(
        description=(
            "CSS selector for the contenteditable target. For TikTok's "
            "caption editor: \"div[contenteditable='true'][role='combobox']\""
        )
    )
    text: str = Field(description="Text to set as the entire field content.")


class GetTextAction(BaseModel):
    """Read the visible text of an element matching a CSS selector."""

    selector: str = Field(description="CSS selector. The first match is used.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _eval_js(browser_session, expression: str) -> dict:
    """Run a JS expression in the active tab. Returns a dict with either
    ``{"value": <serialized>}`` or ``{"error": <message>}``.

    Wraps ``Runtime.evaluate`` with the flags we always want:
    ``returnByValue=True`` so we get a serializable value back, and
    ``awaitPromise=True`` so async JS works.
    """
    cdp_session = await browser_session.get_or_create_cdp_session()
    try:
        result = await cdp_session.cdp_client.send.Runtime.evaluate(
            params={
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
                "userGesture": True,
            },
            session_id=cdp_session.session_id,
        )
    except Exception as exc:
        return {"error": f"CDP transport error: {type(exc).__name__}: {exc}"}

    exc_details = result.get("exceptionDetails")
    if exc_details:
        text = exc_details.get("text") or ""
        exc_obj = exc_details.get("exception") or {}
        desc = exc_obj.get("description") or exc_obj.get("value") or ""
        return {"error": f"{text}: {desc}".strip(": ")}

    res = result.get("result", {})
    if "value" in res:
        return {"value": res["value"]}
    # Some return types (e.g. undefined) come back without a "value" key.
    return {"value": None}


def _summarize_value(val: Any, limit: int = 600) -> str:
    """Render a JS return value as a short string for the agent."""
    try:
        s = json.dumps(val, ensure_ascii=False)
    except Exception:
        s = repr(val)
    return s if len(s) <= limit else s[: limit - 3] + "..."


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def build_tools() -> Tools:
    """Construct a Tools instance with TikTok-publisher-specific actions
    layered on top of browser-use's defaults.

    The default tools are kept (go_to_url, click_element_by_index,
    input_text, scroll, wait, done, ...). We just add four extra
    actions geared for tricky DOM cases.
    """
    tools = Tools()

    @tools.registry.action(
        (
            "Execute JavaScript in the active tab. Use this when the "
            "standard browser-use actions cannot do the job — e.g. "
            "clearing a DraftJS contenteditable, reading internal page "
            "state, matching elements by visible text, dispatching "
            "synthetic events, or interacting with custom widgets. "
            "Both styles work: a bare expression like `document.title`, "
            "or a snippet that uses `return X` (auto-wrapped in an IIFE "
            "for you). The return value is JSON-serialized and returned "
            "as text. On exception you get the error message back, "
            "annotated with a hint about the IIFE wrapping if relevant."
        ),
        param_model=RunJSAction,
    )
    async def run_js(params: RunJSAction, browser_session):
        wrapped = _wrap_js_for_eval(params.code)
        if wrapped != params.code:
            _logger.debug("run_js auto-wrapped code in IIFE")
        result = await _eval_js(browser_session, wrapped)
        if "error" in result:
            err = result["error"]
            hint = ""
            # Defensive: if for some reason the wrapping logic missed
            # a case, surface the IIFE hint to the agent so it can
            # recover next step.
            if "Illegal return" in err or "Unexpected token" in err:
                hint = (
                    " Hint: wrap your code in `(() => { ... })()` if you "
                    "want to use a top-level return statement."
                )
            msg = f"run_js error: {err}{hint}"
            _logger.warning(msg)
            return ActionResult(
                extracted_content=msg,
                long_term_memory=msg[:200],
                error=err,
            )
        text = _summarize_value(result["value"])
        msg = f"run_js -> {text}"
        _logger.info(msg)
        return ActionResult(extracted_content=msg, long_term_memory=msg[:200])

    @tools.registry.action(
        (
            "Click the first visible element whose innerText contains "
            "`text` (case-insensitive). Optionally narrow by ARIA "
            "`role` (e.g. 'button'). Useful when DOM-index click is "
            "unreliable because many elements share the same class. "
            "Returns the element's bounding box on success, or an error "
            "if nothing matched."
        ),
        param_model=ClickByTextAction,
    )
    async def click_by_text(params: ClickByTextAction, browser_session):
        # The JS:
        #  1. Find candidates by role (if given) or all
        #  2. Filter to those visible (offsetParent !== null and bounded)
        #  3. Pick first whose innerText contains the target (case-insensitive)
        #  4. .click() and return its bounding box
        text_json = json.dumps(params.text)
        role_clause = (
            f"el.getAttribute('role') === {json.dumps(params.role)}"
            if params.role
            else "true"
        )
        expr = f"""
        (() => {{
          const target = {text_json}.toLowerCase();
          const all = Array.from(document.querySelectorAll('*'));
          for (const el of all) {{
            if (!{role_clause}) continue;
            if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') continue;
            const t = (el.innerText || el.textContent || '').toLowerCase();
            if (t && t.includes(target)) {{
              const r = el.getBoundingClientRect();
              if (r.width === 0 || r.height === 0) continue;
              el.click();
              return {{ ok: true, tag: el.tagName, role: el.getAttribute('role'), box: {{ x: r.x, y: r.y, w: r.width, h: r.height }} }};
            }}
          }}
          return {{ ok: false, reason: 'no visible element matched' }};
        }})()
        """
        result = await _eval_js(browser_session, expr)
        if "error" in result:
            return ActionResult(
                extracted_content=f"click_by_text error: {result['error']}",
                error=result["error"],
            )
        val = result["value"]
        if isinstance(val, dict) and val.get("ok"):
            msg = f"click_by_text({params.text!r}) -> clicked {val.get('tag')}"
            _logger.info(msg)
            return ActionResult(
                extracted_content=_summarize_value(val), long_term_memory=msg
            )
        return ActionResult(
            extracted_content=f"click_by_text({params.text!r}) -> not found",
            error="not_found",
        )

    @tools.registry.action(
        (
            "Reliably clear and set the content of a contenteditable "
            "element. Built for DraftJS / public-DraftEditor-content "
            "(TikTok's caption field), which silently ignores Ctrl+A + "
            "Delete and ignores `.value = ''`. We focus the element, "
            "use document.execCommand('selectAll' + 'delete'), then "
            "type with execCommand('insertText') so the editor's "
            "internal state stays in sync. Returns the new innerText "
            "for verification."
        ),
        param_model=SetContenteditableAction,
    )
    async def set_contenteditable(
        params: SetContenteditableAction, browser_session
    ):
        sel_json = json.dumps(params.selector)
        text_json = json.dumps(params.text)
        expr = f"""
        (() => {{
          const el = document.querySelector({sel_json});
          if (!el) return {{ ok: false, reason: 'selector did not match' }};
          el.focus();
          // Move caret to end first (some editors anchor selection there)
          const sel = window.getSelection();
          if (sel) {{
            const range = document.createRange();
            range.selectNodeContents(el);
            sel.removeAllRanges();
            sel.addRange(range);
          }}
          // Ask the browser's editing layer to do it. execCommand is
          // deprecated in spec but still the only reliable way to
          // trigger contenteditable mutations DraftJS will accept.
          document.execCommand('selectAll', false, null);
          document.execCommand('delete', false, null);
          document.execCommand('insertText', false, {text_json});
          // Fire input + change for any listeners that don't see exec
          el.dispatchEvent(new InputEvent('input', {{ bubbles: true, inputType: 'insertText', data: {text_json} }}));
          el.dispatchEvent(new Event('change', {{ bubbles: true }}));
          return {{ ok: true, content: el.innerText }};
        }})()
        """
        result = await _eval_js(browser_session, expr)
        if "error" in result:
            return ActionResult(
                extracted_content=f"set_contenteditable error: {result['error']}",
                error=result["error"],
            )
        val = result["value"]
        if isinstance(val, dict) and val.get("ok"):
            content = val.get("content", "")
            ok = content == params.text
            msg = (
                f"set_contenteditable -> content={content!r} "
                f"(matches expected: {ok})"
            )
            _logger.info(msg)
            return ActionResult(extracted_content=msg, long_term_memory=msg[:200])
        return ActionResult(
            extracted_content=f"set_contenteditable -> {val}", error="failed"
        )

    @tools.registry.action(
        (
            "Read the visible text (innerText) of the first element "
            "matching a CSS selector. Useful for verifying that a "
            "previous action took effect (e.g. confirming a caption is "
            "set, or that a date/time field shows the expected value)."
        ),
        param_model=GetTextAction,
    )
    async def get_text(params: GetTextAction, browser_session):
        sel_json = json.dumps(params.selector)
        expr = f"""
        (() => {{
          const el = document.querySelector({sel_json});
          if (!el) return null;
          return el.innerText || el.textContent || '';
        }})()
        """
        result = await _eval_js(browser_session, expr)
        if "error" in result:
            return ActionResult(
                extracted_content=f"get_text error: {result['error']}",
                error=result["error"],
            )
        val = result["value"]
        if val is None:
            return ActionResult(
                extracted_content=f"get_text({params.selector!r}) -> not found",
                error="not_found",
            )
        text = str(val)
        return ActionResult(
            extracted_content=f"get_text({params.selector!r}) -> {text!r}",
            long_term_memory=text[:200],
        )

    return tools


__all__ = ["build_tools"]
