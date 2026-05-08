"""Interactive REPL for testing TikTok publisher tools against a live browser.

Usage (local):    just tiktok-repl
Usage (server):   just prod-tiktok-repl

Commands at the >>> prompt:

    await run_js("document.title")
    await click_by_text("Discard")              # smallest match (index=1)
    await click_by_text("Discard", index=2)      # second-smallest
    await click_by_text("Discard", role="button")
    await set_contenteditable("div[contenteditable='true'][role='combobox']", "Hello")
    await get_text("div[contenteditable='true'][role='combobox']")
    await upload("/path/to/video.mp4")
    await nav("https://...")
    await screenshot()
    await keys("Escape")
"""

from __future__ import annotations

import ast
import asyncio
import base64
import code
import json
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from browser_use import Browser
from playwright_stealth import Stealth

from src.proxies.tiktok_publisher_proxy import (
    STEALTH_BROWSER_ARGS,
    TIKTOK_ALLOWED_DOMAINS,
    TIKTOK_UPLOAD_URL,
    DEFAULT_USER_AGENT,
)
from src.proxies.tiktok_publisher_tools import _eval_js, _wrap_js_for_eval, _summarize_value

COOKIES_PATH = Path(".storage/tiktok_cookies.json")
USER_DATA_DIR = COOKIES_PATH.parent / (COOKIES_PATH.stem + "_userdata")

loop: asyncio.AbstractEventLoop
browser: Browser


def R(coro):
    """Run an async coroutine synchronously."""
    return loop.run_until_complete(coro)


def setup():
    global loop, browser

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not COOKIES_PATH.exists():
        COOKIES_PATH.write_text(json.dumps({"cookies": [], "origins": []}))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    browser = Browser(
        headless=False,
        user_data_dir=str(USER_DATA_DIR),
        args=[*STEALTH_BROWSER_ARGS, "--start-maximized", "--window-size=1920,1080"],
        allowed_domains=TIKTOK_ALLOWED_DOMAINS,
        user_agent=DEFAULT_USER_AGENT,
        keep_alive=True,
        highlight_elements=True,
    )

    print("[browser] launching (may take up to 60s)...")
    R(asyncio.wait_for(browser.start(), timeout=60))
    print("[browser] started")

    stealth_script = Stealth().script_payload
    try:
        R(browser._cdp_add_init_script(stealth_script))
        print("[stealth] injected")
    except Exception as e:
        print(f"[stealth] failed: {e}")


# ── Tool functions ──────────────────────────────────────────────

async def run_js(code_str: str):
    wrapped = _wrap_js_for_eval(code_str)
    result = await _eval_js(browser, wrapped)
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return result["error"]
    val = _summarize_value(result["value"])
    print(f"=> {val}")
    return result["value"]


async def click_by_text(text: str, role: str | None = None, index: int = 1):
    text_json = json.dumps(text)
    role_clause = (
        f"el.getAttribute('role') === {json.dumps(role)}"
        if role else "true"
    )
    js = f"""
    (() => {{
      const target = {text_json}.toLowerCase();
      const idx = {index};
      const all = Array.from(document.querySelectorAll('*'));
      const matches = [];
      for (const el of all) {{
        if (!({role_clause})) continue;
        if (!el.offsetParent && getComputedStyle(el).position !== 'fixed') continue;
        const t = (el.innerText || el.textContent || '').toLowerCase();
        if (t && t.includes(target)) {{
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          matches.push({{ el, area: r.width * r.height }});
        }}
      }}
      if (matches.length === 0) return {{ ok: false, reason: 'no visible element matched' }};
      matches.sort((a, b) => a.area - b.area);
      const pick = idx - 1;
      if (pick < 0 || pick >= matches.length) return {{ ok: false, reason: 'index ' + idx + ' out of range (' + matches.length + ' matches)' }};
      const chosen = matches[pick].el;
      const r = chosen.getBoundingClientRect();
      chosen.click();
      return {{ ok: true, tag: chosen.tagName, role: chosen.getAttribute('role'),
               box: {{ x: r.x, y: r.y, w: r.width, h: r.height }},
               matchIndex: pick + 1, totalMatches: matches.length }};
    }})()
    """
    result = await _eval_js(browser, js)
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        print(f"=> {json.dumps(result['value'], indent=2)}")
    return result.get("value", result.get("error"))


async def set_contenteditable(selector: str, text: str):
    sel_json = json.dumps(selector)
    clean_text = text.replace("\n", " ").replace("\r", " ")
    text_json = json.dumps(clean_text)
    js = f"""
    (() => {{
      const el = document.querySelector({sel_json});
      if (!el) return {{ ok: false, reason: 'selector did not match' }};
      el.focus();
      const sel = window.getSelection();
      if (sel) {{
        const range = document.createRange();
        range.selectNodeContents(el);
        sel.removeAllRanges();
        sel.addRange(range);
      }}
      document.execCommand('selectAll', false, null);
      document.execCommand('delete', false, null);
      document.execCommand('insertText', false, {text_json});
      el.dispatchEvent(new InputEvent('input', {{ bubbles: true, inputType: 'insertText', data: {text_json} }}));
      el.dispatchEvent(new Event('change', {{ bubbles: true }}));
      return {{ ok: true, content: el.innerText }};
    }})()
    """
    result = await _eval_js(browser, js)
    if "error" in result:
        print(f"ERROR: {result['error']}")
    else:
        print(f"=> {json.dumps(result['value'], indent=2)}")
    return result.get("value", result.get("error"))


async def get_text(selector: str):
    return await run_js(
        f"document.querySelector({json.dumps(selector)})?.innerText || '(not found)'"
    )


async def upload(file_path: str):
    """Upload a file to the first <input type=file> on the page."""
    abs_path = str(Path(file_path).resolve())
    if not Path(abs_path).exists():
        print(f"ERROR: file not found: {abs_path}")
        return

    js = """
    (() => {
      const input = document.querySelector('input[type="file"]');
      if (!input) return { ok: false, reason: 'no file input found' };
      return { ok: true, tag: input.tagName };
    })()
    """
    check = await _eval_js(browser, js)
    if "error" in check or not check.get("value", {}).get("ok"):
        print("No <input type=file> found. Trying to reveal one by clicking the drop zone...")
        await run_js("""
            const btn = document.querySelector("button");
            if (btn && /select/i.test(btn.innerText)) btn.click();
        """)
        await asyncio.sleep(1)

    cdp = await browser.get_or_create_cdp_session()

    doc_result = await cdp.cdp_client.send.DOM.getDocument(
        params={}, session_id=cdp.session_id
    )
    root_id = doc_result["root"]["nodeId"]

    query_result = await cdp.cdp_client.send.DOM.querySelector(
        params={"nodeId": root_id, "selector": 'input[type="file"]'},
        session_id=cdp.session_id,
    )
    node_id = query_result.get("nodeId")
    if not node_id:
        print("ERROR: could not find input[type=file] in DOM")
        return

    await cdp.cdp_client.send.DOM.setFileInputFiles(
        params={"nodeId": node_id, "files": [abs_path]},
        session_id=cdp.session_id,
    )
    print(f"[upload] {abs_path}")


async def nav(url: str):
    cdp = await browser.get_or_create_cdp_session()
    await cdp.cdp_client.send.Page.navigate(
        params={"url": url}, session_id=cdp.session_id,
    )
    await asyncio.sleep(3)
    print(f"[nav] {url}")


async def screenshot(path: str = "screenshot.png"):
    cdp = await browser.get_or_create_cdp_session()
    result = await cdp.cdp_client.send.Page.captureScreenshot(
        params={"format": "png"}, session_id=cdp.session_id,
    )
    data = base64.b64decode(result["data"])
    Path(path).write_bytes(data)
    print(f"[screenshot] saved to {path} ({len(data)} bytes)")
    if sys.platform == "darwin":
        os.system(f"open {path}")


async def keys(shortcut: str):
    cdp = await browser.get_or_create_cdp_session()
    for key in shortcut.split("+"):
        await cdp.cdp_client.send.Input.dispatchKeyEvent(
            params={"type": "keyDown", "key": key},
            session_id=cdp.session_id,
        )
    for key in reversed(shortcut.split("+")):
        await cdp.cdp_client.send.Input.dispatchKeyEvent(
            params={"type": "keyUp", "key": key},
            session_id=cdp.session_id,
        )
    print(f"[keys] {shortcut}")


# ── Async-aware REPL ───────────────────────────────────────────

class AsyncConsole(code.InteractiveConsole):
    def runsource(self, source, filename="<input>", symbol="single"):
        source_stripped = source.strip()
        if source_stripped.startswith("await "):
            source_stripped = source_stripped[6:]

        try:
            tree = ast.parse(source_stripped, filename, "eval")
        except SyntaxError:
            return super().runsource(source, filename, symbol)

        compiled = compile(tree, filename, "eval")
        try:
            result = eval(compiled, self.locals)
            if asyncio.iscoroutine(result):
                result = loop.run_until_complete(result)
            if result is not None:
                print(repr(result))
        except SystemExit:
            raise
        except Exception:
            traceback.print_exc()
        return False


# ── Main ───────────────────────────────────────────────────────

def main():
    setup()

    print("\n[nav] going to TikTok Studio...")
    R(nav(TIKTOK_UPLOAD_URL))

    print("\n" + "=" * 60)
    print("TikTok Publisher REPL")
    print("=" * 60)
    print("  await run_js('document.title')")
    print("  await click_by_text('Discard')          # index=1 (smallest)")
    print("  await click_by_text('Discard', index=2)   # second match")
    print("  await set_contenteditable(sel, text)")
    print("  await get_text(selector)")
    print("  await upload('/path/to/video.mp4')")
    print("  await nav('https://...')")
    print("  await screenshot()")
    print("  await keys('Escape')")
    print("=" * 60 + "\n")

    console = AsyncConsole(locals={
        "run_js": run_js,
        "click_by_text": click_by_text,
        "set_contenteditable": set_contenteditable,
        "get_text": get_text,
        "upload": upload,
        "nav": nav,
        "screenshot": screenshot,
        "keys": keys,
        "browser": browser,
    })
    console.interact(banner="", exitmsg="Closing browser...")

    R(browser.stop())
    loop.close()


if __name__ == "__main__":
    main()
