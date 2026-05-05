"""TikTok auto-publisher driven by a browser-use AI agent.

This proxy launches a Chromium instance (via browser-use, with
patchright's stealth-patched binary when available), injects the
playwright-stealth init script to defeat the most common bot
fingerprints, persists cookies between runs via Playwright's
``storage_state``, and asks an OpenRouter-backed LLM agent to drive the
TikTok publishing flow.

The agent is intentionally given a deterministic, step-by-step task —
DeepSeek V4-Flash and other text-only OpenRouter models can follow
those instructions cheaply, but they cannot solve image-based human
verifications. If TikTok puts up a captcha, the agent stops and
reports it, and you can either:

* swap ``TIKTOK_AGENT_MODEL`` for a vision model (e.g.
  ``google/gemini-2.5-flash-lite``), or
* run with ``headless=False`` and solve the captcha manually once
  (the cookies are then saved and reused).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from browser_use import Agent, Browser, ChatOpenAI
from playwright_stealth import Stealth

from src.core.logging_config import get_logger
from src.proxies.interfaces import ITikTokPublisherProxy
from src.proxies.tiktok_publisher_memory import TikTokPublisherMemory
from src.proxies.tiktok_publisher_tools import build_tools

# TikTok only allows scheduling posts up to 10 days in the future via
# the native scheduler in TikTok Studio (Creator/Business accounts).
TIKTOK_SCHEDULE_MAX_DAYS = 10
# TikTok also enforces a minimum gap (~20 min) between "now" and the
# scheduled time. We use a slightly larger buffer to absorb the time it
# takes the agent to upload the file and fill the form.
TIKTOK_SCHEDULE_MIN_MINUTES = 25
# TikTok's time picker is a scroll-wheel with 5-minute granularity in
# the minute column. We snap any user-supplied minute to the nearest
# multiple of 5 (rounding UP so we never end up below the 25-min floor)
# so the value the agent is told to click always exists in the picker.
TIKTOK_SCHEDULE_MINUTE_GRANULARITY = 5

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload?from=upload"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Launch flags borrowed from patchright's defaults that are universally
# safe and meaningfully reduce automation fingerprint surface.
STEALTH_BROWSER_ARGS: List[str] = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-site-isolation-trials",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-dev-shm-usage",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
]

# Domains the agent is allowed to navigate. Any attempt to leave these
# bounds (e.g. an LLM-induced misclick on an external link) will be
# blocked, which also protects the credentials we pass via sensitive_data.
TIKTOK_ALLOWED_DOMAINS: List[str] = [
    "*.tiktok.com",
    "tiktok.com",
    "*.tiktokcdn.com",
    "*.tiktokv.com",
    "*.byteoversea.com",
]


def _build_schedule_steps(schedule_at: datetime) -> str:
    """Schedule-mode tail. Date via native setter, time via cell clicks.

    Empirical: the date input is plain freetext so the React native
    value-setter trick commits cleanly. The time input is bound to a
    wheel picker's internal state — setter triggers re-render which
    snaps back to the wheel position. The only thing that updates the
    wheel is a click on the matching cell.
    """
    iso_date = schedule_at.strftime("%Y-%m-%d")
    hh = schedule_at.strftime("%H")
    mm = schedule_at.strftime("%M")
    return (
        "7. Reveal schedule controls (works in EN or pt-BR):\n"
        "   run_js(code=\"\"\"\n"
        "     const sec = [...document.querySelectorAll('*')].find(el => el.offsetParent && /\\\\b(when to post|quando postar)\\\\b/i.test(el.innerText));\n"
        "     sec?.scrollIntoView({block: 'center'});\n"
        "     const radio = [...document.querySelectorAll('[role=\\\"radio\\\"]')].find(r => r.offsetParent && /\\\\b(schedule|programar)\\\\b/i.test(r.innerText));\n"
        "     radio?.click();\n"
        "     return {scrolled: !!sec, clickedRadio: !!radio};\n"
        "   \"\"\")\n"
        "   If clickedRadio is false, find the schedule radio in the "
        "DOM and click it via click_element_by_index.\n"
        f"8. Set DATE = {iso_date} (date input is freetext; React "
        "native setter works):\n"
        "   run_js(code=\"\"\"\n"
        "     const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;\n"
        "     const i = [...document.querySelectorAll('input[type=\\\"text\\\"]')].filter(x => x.offsetParent).find(x => /^\\\\d{4}-\\\\d{2}-\\\\d{2}$/.test(x.value));\n"
        f"     if (i) {{ set.call(i, '{iso_date}'); ['input','change','blur'].forEach(t => i.dispatchEvent(new Event(t, {{bubbles: true}}))); }}\n"
        "     return i?.value;\n"
        "   \"\"\")\n"
        f"   Expect '{iso_date}'.\n"
        f"9. Set TIME = {hh}:{mm}. The time input is a wheel picker — "
        "native setter snaps back, so click cells:\n"
        "   - Click the time field to open the picker.\n"
        f"   - run_js to click the minute cell '{mm}':\n"
        f"       const cells = [...document.querySelectorAll('div, span, li')].filter(el => el.offsetParent && el.innerText.trim() === '{mm}' && el.getBoundingClientRect().width < 80);\n"
        "       cells[0]?.click();\n"
        "       return cells.length;\n"
        f"   - Same for hour cell '{hh}' if needed.\n"
        f"   - Verify: run_js -> return [...document.querySelectorAll"
        "('input')].find(i => /^\\\\d{2}:\\\\d{2}$/.test(i.value))?.value; "
        f"— must be '{hh}:{mm}'.\n"
        "10. click_by_text 'Schedule' or 'Agendar' (NOT 'Post' / "
        "'Postar'). Single action.\n"
        "11. Wait for 'Video scheduled' / 'Vídeo agendado' or /manage "
        "redirect, then done(success=True, text=<URL>).\n"
    )


class BrowserUseTikTokPublisherProxy(ITikTokPublisherProxy):
    """Auto-publish videos to TikTok using a browser-use AI agent."""

    def __init__(
        self,
        email: str,
        password: str,
        openrouter_api_key: str,
        model: str,
        cookies_path: str = ".storage/tiktok_cookies.json",
        headless: bool = False,
        max_steps: int = 60,
        use_vision: bool = False,
    ) -> None:
        if not email:
            raise ValueError("TIKTOK_EMAIL is required for the TikTok publisher")
        if not password:
            raise ValueError("TIKTOK_PASSWORD is required for the TikTok publisher")
        if not openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required for the TikTok publisher agent"
            )

        self._logger = get_logger(__name__)
        self._email = email
        self._password = password
        self._openrouter_api_key = openrouter_api_key
        self._model = model
        self._headless = headless
        self._max_steps = max_steps
        self._use_vision = use_vision

        # We persist via Chromium's `user_data_dir` (sibling of the
        # storage_state file). This captures cookies, localStorage,
        # IndexedDB and Service Workers — everything TikTok uses for
        # device-trust and session restoration. A plain Playwright
        # storage_state JSON is too narrow: TikTok stores critical
        # auth tokens in localStorage that storage_state also captures
        # but only if a logged-in session was ever flushed to it.
        cookies_path_obj = Path(cookies_path).expanduser().resolve()
        cookies_path_obj.parent.mkdir(parents=True, exist_ok=True)
        self._cookies_path = cookies_path_obj
        self._user_data_dir = cookies_path_obj.parent / (
            cookies_path_obj.stem + "_userdata"
        )
        self._user_data_dir.mkdir(parents=True, exist_ok=True)
        if not self._cookies_path.exists():
            # Keep a Playwright-compatible export alongside the user_data_dir
            # so other tooling can introspect the session if needed.
            self._cookies_path.write_text(
                json.dumps({"cookies": [], "origins": []})
            )

        # The memory module owns run capture (rich JSON + markdown
        # trace per run, no LLM reflection). Files land under the same
        # .storage/ dir as the cookies, so a single rsync of
        # .storage/tiktok_runs/ + .storage/tiktok_learnings.md is
        # enough to inspect prod runs from the dev machine.
        self._memory = TikTokPublisherMemory(base_dir=cookies_path_obj.parent)

        # Bump LLM-related loggers to DEBUG so the per-run bootstrap log
        # captures raw HTTP traffic to OpenRouter (request bodies +
        # response bodies). When browser-use's strict JSON parser fails,
        # the actual model output appears in these debug lines and we
        # can see exactly what the model returned. Idempotent: setting
        # the same level twice is a no-op.
        self._enable_debug_logging()

    @staticmethod
    def _enable_debug_logging() -> None:
        """Bump LLM-related loggers to DEBUG level.

        Cheap, idempotent. The bootstrap helper tees stdout+stderr to a
        per-run ``.storage/tiktok_runs/<ts>-bootstrap.log`` so the
        verbose lines land in a synced file. We previously also
        monkey-patched ``openai.AsyncCompletions.create`` to dump raw
        responses, but that was only needed to diagnose the
        gpt-5.4-mini JSON-mode bug — the patch is removed now.
        """
        for name in ("browser_use", "httpx", "httpcore", "openai", "litellm"):
            logging.getLogger(name).setLevel(logging.DEBUG)

    async def publish_video(
        self,
        video_path: str,
        description: str,
        hashtags: Optional[List[str]] = None,
        schedule_at: Optional[datetime] = None,
    ) -> str:
        absolute_video_path = os.path.abspath(video_path)
        if not os.path.exists(absolute_video_path):
            raise FileNotFoundError(f"Video not found: {absolute_video_path}")

        if schedule_at is not None:
            schedule_at = self._validate_schedule_at(schedule_at)
            self._logger.info(
                "Scheduling TikTok post for %s",
                schedule_at.strftime("%Y-%m-%d %H:%M"),
            )

        full_description = self._format_description(description, hashtags)

        # Note: we intentionally do NOT pass executable_path. Forcing
        # patchright's "Google Chrome for Testing" build alongside a
        # persistent user_data_dir was found to crash the CDP target
        # almost immediately on TikTok (Session-with-given-id-not-found
        # cascade). browser-use's default Chromium pick is more stable;
        # stealth still applies via the playwright-stealth init script
        # injected below and the launch args.
        browser = Browser(
            headless=self._headless,
            user_data_dir=str(self._user_data_dir),
            args=STEALTH_BROWSER_ARGS,
            allowed_domains=TIKTOK_ALLOWED_DOMAINS,
            user_agent=DEFAULT_USER_AGENT,
            keep_alive=False,
            highlight_elements=False,
            # Tuned down from the original belt-and-suspenders 3.0/2.0
            # values. The original CDP-target-not-found cascade we saw
            # was caused by forcing patchright's executable_path with a
            # persistent user_data_dir, not by short waits — so we can
            # safely run the page-load waits at near-default values now.
            wait_for_network_idle_page_load_time=1.5,
            minimum_wait_page_load_time=0.5,
        )

        llm = ChatOpenAI(
            model=self._model,
            base_url=OPENROUTER_BASE_URL,
            api_key=self._openrouter_api_key,
            temperature=0.1,
        )

        task = self._build_task(absolute_video_path, full_description, schedule_at)

        # Custom tools: run_js, click_by_text, set_contenteditable, get_text.
        # Layered on top of browser-use's defaults so the agent can fall
        # back to JS when standard actions hit weird DOM cases (DraftJS,
        # scroll-wheel pickers, lookalike sidebars, etc.).
        tools = build_tools()

        # Open the live log BEFORE the agent runs so per-step writes
        # land in a known file even if the process crashes mid-run.
        live_log_path = self._memory.start_live_log(
            video_path=absolute_video_path,
            description=full_description,
            schedule_at=schedule_at,
        )
        self._logger.info("TikTok live log: %s", live_log_path)

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            tools=tools,
            available_file_paths=[absolute_video_path],
            sensitive_data={
                "tiktok_email": self._email,
                "tiktok_password": self._password,
            },
            use_vision=self._use_vision,
            register_new_step_callback=self._make_step_callback(),
        )

        history = None
        outcome = "unknown"
        try:
            await self._start_session_with_stealth(agent)
            history = await agent.run(max_steps=self._max_steps)
            final_url = self._extract_url(history)
            done_ok = self._extract_done_success(history)
            if done_ok is True:
                outcome = "success"
            elif done_ok is False:
                # Agent explicitly called done(success=False). The text
                # in final_url is the failure reason, not a URL.
                outcome = "agent_reported_failure"
            else:
                # No done() at all — agent ran out of steps or crashed.
                outcome = "no_done_call"
            return final_url
        except Exception as exc:
            outcome = f"error_{type(exc).__name__}"
            raise
        finally:
            # Best-effort: capture the run regardless of success or
            # failure. We dump:
            #   * <ts>-<outcome>.json  — structured per-step record
            #   * <ts>-<outcome>.md    — human-readable trace
            # No LLM-based reflection — humans drive the prompt edits.
            try:
                self._memory.capture_run(
                    history=history,
                    outcome=outcome,
                    video_path=absolute_video_path,
                    description=full_description,
                    schedule_at=schedule_at,
                )
            except Exception as exc:
                self._logger.warning(
                    "TikTok memory bookkeeping failed: %s", exc
                )
            await self._safe_stop(browser)

    def _make_step_callback(self):
        """Return an async callback that flushes each step to the live log.

        browser-use fires this AFTER the LLM produces ``model_output`` for
        a step but BEFORE the actions are dispatched, so we capture the
        agent's intent (thinking / eval / memory / next_goal / planned
        actions). We do NOT see the action results here — those land in
        the agent's history at the end of the step. The end-of-run
        ``capture_run`` call (in publish_video's ``finally``) writes the
        complete picture; the live log is here purely so we still have
        the agent's step-by-step decisions on disk if the process dies
        mid-run.
        """
        memory = self._memory
        logger = self._logger

        async def callback(browser_state, model_output, n_steps):
            try:
                actions = []
                try:
                    for a in (getattr(model_output, "action", None) or []):
                        if hasattr(a, "model_dump"):
                            d = a.model_dump(exclude_none=True)
                            if isinstance(d, dict) and len(d) == 1:
                                name, params = next(iter(d.items()))
                                actions.append({"name": name, "params": params})
                            else:
                                actions.append(d)
                except Exception:
                    pass

                step_record = {
                    "step": n_steps,
                    "url": getattr(browser_state, "url", None),
                    "thinking": getattr(model_output, "thinking", "") or "",
                    "eval": getattr(model_output, "evaluation_previous_goal", "") or "",
                    "memory": getattr(model_output, "memory", "") or "",
                    "next_goal": getattr(model_output, "next_goal", "") or "",
                    "actions_planned": actions,
                }
                memory.append_live_step(step_record)
            except Exception as exc:
                logger.warning("Step callback failed: %s", exc)

        return callback

    async def _start_session_with_stealth(self, agent: Agent) -> None:
        """Boot the browser and inject playwright-stealth init scripts.

        browser-use lazily starts the BrowserSession on the first action,
        but we need the stealth script to be registered before any
        navigation so that ``navigator.webdriver`` and friends are
        already patched on the first document. We start the session
        ourselves and then add the script via CDP.
        """
        session = agent.browser_session
        assert session is not None, "Agent did not initialize browser_session"
        await session.start()

        stealth_script = Stealth().script_payload
        try:
            await session._cdp_add_init_script(stealth_script)  # noqa: SLF001
            self._logger.info("Injected playwright-stealth init script")
        except Exception as exc:
            self._logger.warning("Failed to inject stealth script: %s", exc)

    @staticmethod
    async def _safe_stop(browser: Browser) -> None:
        """Stop the browser with hard timeouts, swallowing teardown errors.

        browser-use's storage_state watchdog flushes cookies to disk on
        the ``BrowserStopEvent``, so a clean ``stop()`` is what persists
        the TikTok session for the next run. However, when the agent has
        wrecked the page state (e.g. left dangling popups, lost CDP
        targets), ``stop()`` can hang for several minutes waiting on a
        flush that will never complete — bad UX when the user just hit
        Ctrl+C. We give ``stop()`` 15 s to finish gracefully, then fall
        back to ``kill()`` (5 s budget); past that we move on regardless.
        """
        logger = get_logger(__name__)
        try:
            await asyncio.wait_for(browser.stop(), timeout=15.0)
            return
        except asyncio.TimeoutError:
            logger.warning(
                "browser.stop() exceeded 15s — forcing kill (session "
                "state may not have flushed cleanly)"
            )
        except Exception as exc:
            logger.warning("browser.stop() raised %s — forcing kill", exc)

        try:
            await asyncio.wait_for(browser.kill(), timeout=5.0)
        except Exception:
            logger.warning(
                "browser.kill() also failed — leaking the Chromium "
                "process; the OS will reap it"
            )

    @staticmethod
    def _format_description(
        description: str, hashtags: Optional[List[str]]
    ) -> str:
        if not hashtags:
            return description.strip()
        tag_str = " ".join(f"#{h.lstrip('#')}" for h in hashtags)
        if not description.strip():
            return tag_str
        return f"{description.strip()}\n\n{tag_str}"

    @staticmethod
    def _build_task(
        video_path: str,
        description: str,
        schedule_at: Optional[datetime],
        lessons: str = "",  # noqa: ARG004 — currently unused, kept for API stability
    ) -> str:
        """Build a tight task prompt (~1.5 KB) for a text-only LLM.

        Design rule of thumb: prompts that are 5+ KB drown the agent.
        DeepSeek V4-Flash starts hallucinating retries on Step 5 when
        the prompt is too verbose. This version cuts everything we
        learned the agent already infers from the DOM dump on its own,
        and keeps ONLY the things we know it gets wrong without help:

          * which sidebar buttons to ignore (all look the same in DOM)
          * "upload-fire-and-forget" (it tries 4× otherwise)
          * "DraftJS caption needs ``input_text(clear_existing=True)``"
            — manual Ctrl+A + Delete is silently swallowed by DraftJS
          * "time picker is a scroll wheel" — typing into it is a no-op
          * no todo.md busywork
        """
        if schedule_at is not None:
            schedule_block = _build_schedule_steps(schedule_at)
        else:
            schedule_block = (
                "7. click_by_text 'Post' or 'Postar' (single action).\n"
                "8. Wait for confirmation, done(success=True, text=<URL>).\n"
            )

        return (
            "# TikTok Studio publish task (UI may be EN or pt-BR)\n"
            "\n"
            "Session is logged in unless redirected to /login. If an "
            "action fails 3× in a row, done(success=False). NEVER "
            "re-navigate to /upload — you'll lose progress.\n"
            "\n"
            "## Custom actions\n"
            "- run_js(code) — JS in the active tab. Top-level `return X` "
            "is auto-wrapped in an IIFE. Returns JSON-serializable values.\n"
            "- click_by_text(text, role?) — click the first visible "
            "element whose innerText contains `text` (case-insensitive).\n"
            "- set_contenteditable(selector, text) — clear+set a "
            "contenteditable. USE FOR CAPTION (input_text doesn't clear "
            "DraftJS).\n"
            "- get_text(selector) — read innerText for verification.\n"
            "\n"
            "## Hard rules\n"
            "- Caption is DraftJS — set_contenteditable only.\n"
            "- Time-picker cells: click them. React native value-setting "
            "snaps back.\n"
            "- Sidebar (class Sidebar_Sidebar_Clickable, 4 lookalike "
            "buttons): never click.\n"
            "- upload_file_to_element: call once, then wait(8).\n"
            "- Multi-action sequences: never put a page-changing action "
            "(submit click, modal-closer) anywhere but the LAST slot — "
            "subsequent actions get dropped.\n"
            "- No write_file / replace_file_str / read_file. No todo.md.\n"
            "\n"
            "## JS recipes (use with run_js when needed)\n"
            "# Read caption (verify):\n"
            "  return document.querySelector(\"div[contenteditable='true'][role='combobox']\").innerText;\n"
            "# List visible buttons (discovery):\n"
            "  return [...document.querySelectorAll('button')].filter(b => b.offsetParent && b.innerText.trim()).slice(0,20).map(b => b.innerText.trim().slice(0,40));\n"
            "\n"
            "## Steps\n"
            f"1. go_to_url('{TIKTOK_UPLOAD_URL}'); wait(3).\n"
            "2. If /login: click_by_text 'Use phone' or 'Usar telefone', "
            "then 'Email' or 'e-mail'. input_text email=`tiktok_email`, "
            "password=`tiktok_password`. click_by_text 'Log in' or "
            "'Entrar'. On captcha (slider): wait(30), recheck URL, ≤4×.\n"
            "3. Dismiss any visible overlay: 'Continue editing?' (click "
            "Discard), 'Got it' / 'Pronto' (click the button).\n"
            f"4. upload_file_to_element on the drop zone (`<div "
            f"role='button'>` containing 'Select video' / 'Selecionar "
            f"vídeo' / 'Drag and drop'), path='{video_path}'. wait(8).\n"
            "5. (OPTIONAL — max 2 attempts, then skip) Cover:\n"
            "   - click_by_text 'Edit cover' or 'Editar capa'.\n"
            "   - run_js to click the leftmost thumbnail:\n"
            "       return [...document.querySelectorAll('div[role=\"dialog\"] [role=\"button\"]')].filter(el => el.offsetParent && el.getBoundingClientRect().width < 100).sort((a,b) => a.getBoundingClientRect().x - b.getBoundingClientRect().x)[0]?.click() ? 'ok' : 'no thumbnail';\n"
            "   - click_by_text 'Save' or 'Salvar'.\n"
            "   - On any failure: send_keys('Escape'), continue.\n"
            f"6. Caption: set_contenteditable(selector=\"div[contenteditable"
            f"='true'][role='combobox']\", text='{description}'). Then "
            "get_text on the same selector — must equal the text exactly.\n"
            f"{schedule_block}"
        )

    @staticmethod
    def _validate_schedule_at(schedule_at: datetime) -> datetime:
        """Ensure the requested scheduled time is within TikTok's window.

        TikTok rejects scheduled times that are too close to "now"
        (~20 min minimum) or further than 10 days in the future. We
        normalise naive datetimes to local time and enforce the bounds
        eagerly so the agent never wastes steps fighting the UI.

        We also snap the minute UP to the nearest 5-minute boundary
        because TikTok's time picker is a scroll wheel with 5-minute
        granularity. Asking the agent to "click 13:07" when the picker
        only has 13:05 / 13:10 cells wastes steps. Rounding UP guarantees
        we never accidentally drop below the min-time floor.
        """
        if schedule_at.tzinfo is not None:
            # Normalise to local time — TikTok Studio always uses the
            # browser's local timezone for the date/time picker.
            schedule_at = schedule_at.astimezone().replace(tzinfo=None)

        # Snap to the next 5-minute mark (always upward, drop seconds).
        granularity = TIKTOK_SCHEDULE_MINUTE_GRANULARITY
        schedule_at = schedule_at.replace(second=0, microsecond=0)
        remainder = schedule_at.minute % granularity
        if remainder != 0:
            schedule_at = schedule_at + timedelta(minutes=granularity - remainder)

        now = datetime.now()
        min_time = now + timedelta(minutes=TIKTOK_SCHEDULE_MIN_MINUTES)
        max_time = now + timedelta(days=TIKTOK_SCHEDULE_MAX_DAYS)

        if schedule_at < min_time:
            raise ValueError(
                "TikTok requires the scheduled time to be at least "
                f"{TIKTOK_SCHEDULE_MIN_MINUTES} minutes in the future. "
                f"Got {schedule_at:%Y-%m-%d %H:%M}, "
                f"earliest allowed is {min_time:%Y-%m-%d %H:%M}."
            )
        if schedule_at > max_time:
            raise ValueError(
                "TikTok only allows scheduling up to "
                f"{TIKTOK_SCHEDULE_MAX_DAYS} days in advance. "
                f"Got {schedule_at:%Y-%m-%d %H:%M}, "
                f"latest allowed is {max_time:%Y-%m-%d %H:%M}."
            )
        return schedule_at

    @staticmethod
    def _extract_url(history) -> str:
        try:
            final = history.final_result()
            if isinstance(final, str):
                return final
        except Exception:
            pass
        return ""

    @staticmethod
    def _extract_done_success(history) -> Optional[bool]:
        """Return True / False if the agent called ``done(success=...)``,
        or None if there was no done() call at all.

        ``history.final_result()`` returns the text of the last done()
        even when ``success=False`` — without this check we'd mis-tag
        "agent gave up with an error message" runs as ``success``.
        """
        try:
            history_list = getattr(history, "history", None) or []
            for step in reversed(history_list):
                model_output = getattr(step, "model_output", None)
                if model_output is None:
                    continue
                actions = getattr(model_output, "action", None) or []
                for action in actions:
                    if not hasattr(action, "model_dump"):
                        continue
                    d = action.model_dump(exclude_none=True)
                    if isinstance(d, dict) and "done" in d:
                        return bool(d["done"].get("success", False))
        except Exception:
            pass
        return None

    @staticmethod
    def _find_patchright_chromium() -> Optional[str]:
        """Locate the patchright-installed Chromium binary, if any.

        patchright shares Playwright's cache directory but installs its
        own chromium-* folder. We use the newest one available so that
        browser-use launches a Chromium build that is closer to a real
        user's browser than the headless shell.
        """
        cache_roots = [
            Path.home() / "Library" / "Caches" / "ms-playwright",
            Path.home() / ".cache" / "ms-playwright",
            Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")),
        ]

        glob_patterns = (
            "chromium-*/chrome-mac-arm64/*.app/Contents/MacOS/*",
            "chromium-*/chrome-mac/*.app/Contents/MacOS/*",
            "chromium-*/chrome-linux64/chrome",
            "chromium-*/chrome-linux/chrome",
            "chromium-*/chrome-win/chrome.exe",
        )

        for root in cache_roots:
            if not root or not root.exists():
                continue
            for pattern in glob_patterns:
                matches = sorted(root.glob(pattern))
                if matches:
                    return str(matches[-1])
        return None


__all__ = ["BrowserUseTikTokPublisherProxy"]
