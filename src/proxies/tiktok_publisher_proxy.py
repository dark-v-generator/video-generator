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
    iso_date = schedule_at.strftime("%Y-%m-%d")
    day = str(schedule_at.day)
    hh = schedule_at.strftime("%H")
    mm = schedule_at.strftime("%M")
    return (
        "7. Scroll 'When to post' into view and click 'Schedule' radio. "
        "A time picker may auto-open — ignore it and proceed.\n"
        f"8. Call `set_schedule_date(day='{day}')` to set date to {iso_date}.\n"
        f"9. Call `set_schedule_time(hour='{hh}', minute='{mm}')` to set time.\n"
        f"10. Call `get_schedule_values()` to verify it shows {hh}:{mm} and {iso_date}.\n"
        "11. Call `scroll_to_submit()`, then `click_by_text(text='Schedule', role='button')`.\n"
        "12. Wait for confirmation or /manage redirect, "
        "then done(success=True, text=<confirmation or URL>).\n"
    )


class BrowserUseTikTokPublisherProxy(ITikTokPublisherProxy):
    """Auto-publish videos to TikTok using a browser-use AI agent."""

    def __init__(
        self,
        openrouter_api_key: str,
        model: str,
        cookies_path: str = ".storage/tiktok_cookies.json",
        headless: bool = False,
        max_steps: int = 60,
        use_vision: bool = False,
    ) -> None:
        if not openrouter_api_key:
            raise ValueError(
                "OPENROUTER_API_KEY is required for the TikTok publisher agent"
            )

        self._logger = get_logger(__name__)
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
            highlight_elements=True,
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

        run_ts = Path(live_log_path).stem.split(".")[0]
        runs_dir = Path(live_log_path).parent
        gif_path = str(runs_dir / f"{run_ts}.gif")
        conversation_path = str(runs_dir / f"{run_ts}-conversation.json")
        self._logger.info("TikTok debug GIF: %s", gif_path)
        self._logger.info("TikTok conversation log: %s", conversation_path)

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            tools=tools,
            available_file_paths=[absolute_video_path],
            use_vision=self._use_vision,
            register_new_step_callback=self._make_step_callback(),
            llm_timeout=180,
            generate_gif=gif_path,
            save_conversation_path=conversation_path,
        )

        history = None
        outcome = "unknown"
        try:
            await self._start_session_with_stealth(agent)
            history = await agent.run(max_steps=self._max_steps)

            errors = self._count_errors(history)
            final_text = self._extract_url(history)
            done_ok = self._extract_done_success(history)
            last_url = self._extract_last_url(history)

            self._logger.info(
                "TikTok agent finished: done=%s, errors=%d/%d steps, "
                "last_url=%s, final_text=%.200s",
                done_ok,
                errors["failed_steps"],
                errors["total_steps"],
                last_url,
                final_text,
            )
            if errors["failed_steps"] > 0:
                self._logger.warning(
                    "TikTok agent had %d failed steps out of %d: %s",
                    errors["failed_steps"],
                    errors["total_steps"],
                    errors["error_messages"],
                )

            if done_ok is True:
                if not self._looks_like_success(final_text, last_url):
                    outcome = "false_positive"
                    raise RuntimeError(
                        f"TikTok agent claimed success but result doesn't "
                        f"look right. final_text={final_text!r}, "
                        f"last_url={last_url!r}, "
                        f"errors={errors['failed_steps']}/{errors['total_steps']}"
                    )
                outcome = "success"
                return final_text
            elif done_ok is False:
                outcome = "agent_reported_failure"
                raise RuntimeError(
                    f"TikTok agent reported failure: {final_text or 'no details'}"
                )
            else:
                outcome = "no_done_call"
                raise RuntimeError(
                    "TikTok agent did not complete — ran out of steps or crashed"
                )
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
        return f"{description.strip()}  {tag_str}"

    @staticmethod
    def _build_task(
        video_path: str,
        description: str,
        schedule_at: Optional[datetime],
        lessons: str = "",  # noqa: ARG004 — currently unused, kept for API stability
    ) -> str:
        """Build a minimal task prompt for the browser agent.

        Only specifies the goal and genuinely tricky parts. The agent
        decides how to interact with the UI on its own.
        """
        if schedule_at is not None:
            schedule_block = _build_schedule_steps(schedule_at)
        else:
            schedule_block = (
                "4. Click 'Post' / 'Postar' to publish immediately.\n"
                "5. Wait for confirmation, "
                "then done(success=True, text=<confirmation or URL>).\n"
            )

        return (
            "# Publish a video on TikTok Studio\n"
            "\n"
            "Session is already logged in. DO NOT create todo.md or any "
            "planning files — execute steps directly.\n"
            "\n"
            "IMPORTANT: For scheduling (date/time), ONLY use the "
            "set_schedule_date and set_schedule_time tools. Do NOT try "
            "to click time picker elements by index — the scroll-wheel "
            "picker elements are not reliably clickable that way.\n"
            "\n"
            "## Your TikTok-specific tools\n"
            "Use these instead of crafting JS yourself:\n"
            "- `dismiss_overlay()` — checks for 'Continue editing?' overlay "
            "and clicks both Discard buttons automatically.\n"
            "- `set_contenteditable(selector, text)` — clear+fill a DraftJS "
            "field. Use selector: div[contenteditable='true'][role='combobox']\n"
            "- `select_cover_frame()` — opens Edit Cover, picks the first "
            "frame, and clicks Save. Call after upload finishes.\n"
            "- `set_schedule_date(day)` — opens the date picker and clicks "
            "a day number (e.g. day='15').\n"
            "- `set_schedule_time(hour, minute)` — opens time picker, clicks "
            "hour+minute, closes picker (e.g. hour='13', minute='30').\n"
            "- `get_schedule_values()` — reads current [time, date] from inputs.\n"
            "- `scroll_to_submit()` — scrolls the Schedule/Post button into view.\n"
            "- `click_by_text(text, role?, index?)` — click element by text.\n"
            "- `upload_video(file_path)` — upload a video via CDP. Handles "
            "finding the hidden file input automatically.\n"
            "- `run_js(code)` — run arbitrary JS if needed.\n"
            "\n"
            "## Steps\n"
            f"1. Go to {TIKTOK_UPLOAD_URL}\n"
            "2. Call `dismiss_overlay()` to clear any leftover draft.\n"
            f"3. Call `upload_video(file_path='{video_path}')`.\n"
            "4. Wait 8 seconds for the upload to process.\n"
            f"5. Set the caption (one line, no newlines):\n{description}\n"
            "6. Call `select_cover_frame()` to fix the black cover.\n"
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
    def _extract_last_url(history) -> str:
        """Return the browser URL from the last step that had one."""
        try:
            for step in reversed(getattr(history, "history", None) or []):
                state = getattr(step, "state", None)
                url = getattr(state, "url", None)
                if url:
                    return url
        except Exception:
            pass
        return ""

    @staticmethod
    def _count_errors(history) -> dict:
        """Summarise step-level errors from the run history."""
        total = 0
        failed = 0
        messages: List[str] = []
        try:
            for step in getattr(history, "history", None) or []:
                total += 1
                errs = getattr(step, "errors", None) or []
                if errs:
                    failed += 1
                    for e in errs[:2]:
                        msg = str(e)[:120]
                        if msg not in messages:
                            messages.append(msg)
        except Exception:
            pass
        return {
            "total_steps": total,
            "failed_steps": failed,
            "error_messages": messages[:10],
        }

    @staticmethod
    def _looks_like_success(final_text: str, last_url: str) -> bool:
        """Sanity-check whether the run actually scheduled/posted a video.

        The agent should end on a /manage page or report a confirmation
        like "Video scheduled". If neither is true, the agent lied.
        """
        text_lower = final_text.lower()
        url_lower = last_url.lower()

        success_signals = (
            "/manage" in url_lower,
            "scheduled" in text_lower,
            "agendado" in text_lower,
            "posted" in text_lower,
            "publicado" in text_lower,
            "tiktok.com" in text_lower,
        )
        return any(success_signals)

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
