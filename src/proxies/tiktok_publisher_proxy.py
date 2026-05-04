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

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from browser_use import Agent, Browser, ChatOpenAI
from playwright_stealth import Stealth

from src.core.logging_config import get_logger
from src.proxies.interfaces import ITikTokPublisherProxy

# TikTok only allows scheduling posts up to 10 days in the future via
# the native scheduler in TikTok Studio (Creator/Business accounts).
TIKTOK_SCHEDULE_MAX_DAYS = 10
# TikTok also enforces a minimum gap (~20 min) between "now" and the
# scheduled time. We use a slightly larger buffer to absorb the time it
# takes the agent to upload the file and fill the form.
TIKTOK_SCHEDULE_MIN_MINUTES = 25

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
    """Render the agent instructions for the TikTok scheduler UI.

    The TikTok Studio scheduler is a calendar + time grid: clicking
    "Schedule" reveals a radio toggle ("Now" vs "Schedule"), then a
    date input (calendar popup, click the day cell) and a time input
    (HH:MM grid). We give the agent the explicit target values so it
    does not have to reason about formats.
    """
    iso_date = schedule_at.strftime("%Y-%m-%d")
    human_date = schedule_at.strftime("%B %d, %Y").replace(" 0", " ")
    day_number = str(schedule_at.day)
    hh_mm_24 = schedule_at.strftime("%H:%M")
    hh_mm_12 = schedule_at.strftime("%I:%M %p").lstrip("0")

    return (
        "   d. Find the 'When to post' / 'Schedule' section near the "
        "bottom of the right-hand form. Select the 'Schedule' radio "
        "option (the alternative is 'Now').\n"
        "   e. A date input and a time input will appear. Set them so "
        f"the post is scheduled for {iso_date} at {hh_mm_24} (24h) — "
        f"i.e. {human_date} at {hh_mm_12} in the user's local timezone.\n"
        "      - Click the date input. In the calendar popup that "
        f"appears, click the day cell labelled '{day_number}' for the "
        f"month of {schedule_at.strftime('%B %Y')}. If the calendar is "
        "showing a different month, use the arrow buttons to move "
        "until the right month is visible. If the day is greyed out, "
        "TikTok considers it outside the 10-day window — STOP and "
        "report the issue.\n"
        "      - Click the time input. Either type "
        f"'{hh_mm_24}' directly, or in the time picker grid select "
        f"hour '{schedule_at.strftime('%H')}' and minute "
        f"'{schedule_at.strftime('%M')}'.\n"
        "   f. Verify that the date/time inputs now display the values "
        f"{iso_date} and {hh_mm_24} (or the 12h equivalent). If they do "
        "not, retry once.\n"
        "   g. Click the 'Schedule' button (it replaces the 'Post' "
        "button when scheduling is selected). Do NOT click 'Post Now'.\n"
        "4. Wait for a confirmation message such as 'Video scheduled' "
        "or a redirect to 'Manage posts'.\n"
        "5. Return the scheduled-post URL if visible on the page; "
        "otherwise return the final page URL.\n"
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
            wait_for_network_idle_page_load_time=3.0,
            minimum_wait_page_load_time=2.0,
        )

        llm = ChatOpenAI(
            model=self._model,
            base_url=OPENROUTER_BASE_URL,
            api_key=self._openrouter_api_key,
            temperature=0.1,
        )

        task = self._build_task(absolute_video_path, full_description, schedule_at)

        agent = Agent(
            task=task,
            llm=llm,
            browser=browser,
            available_file_paths=[absolute_video_path],
            sensitive_data={
                "tiktok_email": self._email,
                "tiktok_password": self._password,
            },
            use_vision=self._use_vision,
        )

        try:
            await self._start_session_with_stealth(agent)
            history = await agent.run(max_steps=self._max_steps)
            return self._extract_url(history)
        finally:
            await self._safe_stop(browser)

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
        """Stop the browser, swallowing teardown errors.

        browser-use's storage_state watchdog flushes cookies to disk on
        the BrowserStopEvent, so calling ``stop`` is what persists the
        TikTok session for the next run.
        """
        try:
            await browser.stop()
        except Exception:
            try:
                await browser.kill()
            except Exception:
                pass

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
    ) -> str:
        # Heredoc-style task. Keep instructions tight and deterministic
        # so cheap text-only models can follow them without ambiguity.
        if schedule_at is not None:
            final_action = _build_schedule_steps(schedule_at)
        else:
            final_action = (
                "   d. Click the 'Post' or 'Publish' button.\n"
                "4. Wait for a confirmation page (e.g. 'Manage posts', "
                "'Your video has been uploaded', 'Posted successfully').\n"
                "5. Return the URL of the published video if visible on "
                "the page; otherwise return the final page URL.\n"
            )

        return (
            "You are an automation agent publishing a video to TikTok.\n"
            "Follow these steps in order. Do not improvise extra steps.\n"
            "\n"
            f"1. Navigate to {TIKTOK_UPLOAD_URL}\n"
            "2. If the page redirects to a login screen (URL contains "
            "'/login') or shows a 'Log in' form:\n"
            "   a. Click any tab labelled 'Use phone / email / username' "
            "or 'Usar telefone / e-mail / nome de usuário'.\n"
            "   b. Click the 'Email / Username' tab if it exists "
            "(in pt-BR: 'Entrar com nome de usuário ou e-mail').\n"
            "   c. Type the placeholder `tiktok_email` into the "
            "email/username input.\n"
            "   d. Type the placeholder `tiktok_password` into the "
            "password input.\n"
            "   e. Click the 'Log in' / 'Entrar' submit button.\n"
            "   f. If a captcha or slider verification widget appears "
            "(image puzzle, 'Drag the slider', 'Arraste o controle "
            "deslizante', etc.):\n"
            "      - Do NOT attempt to guess or click drag targets.\n"
            "      - Use the wait action with seconds=30 up to 4 times "
            "(120 s total). A human is watching the browser and will "
            "solve the puzzle manually.\n"
            "      - After each wait, re-evaluate the page: if the URL "
            "now contains '/tiktokstudio' or '/foryou', the captcha was "
            "solved — proceed to step 3.\n"
            "      - If after 4 waits the captcha is still present, "
            "report what you see and stop.\n"
            "   g. After login, you may be redirected to the TikTok "
            f"home page instead of the upload page. If so, navigate to "
            f"{TIKTOK_UPLOAD_URL} again before continuing.\n"
            "3. Once on the studio upload page (URL contains "
            "'/tiktokstudio/upload'):\n"
            "   a. Use the upload_file_to_element action to upload the "
            f"local file `{video_path}` into the visible video upload "
            "input.\n"
            "   b. Wait until the upload progress bar disappears and a "
            "video preview / 'Cover' panel becomes visible (this can take "
            "up to 60 seconds for short clips).\n"
            "   c. Find the description / caption editor (an empty "
            "contenteditable area at the top of the right-hand form) and "
            "type EXACTLY the following text:\n"
            "\n"
            f"{description}\n"
            "\n"
            f"{final_action}"
        )

    @staticmethod
    def _validate_schedule_at(schedule_at: datetime) -> datetime:
        """Ensure the requested scheduled time is within TikTok's window.

        TikTok rejects scheduled times that are too close to "now"
        (~20 min minimum) or further than 10 days in the future. We
        normalise naive datetimes to local time and enforce the bounds
        eagerly so the agent never wastes steps fighting the UI.
        """
        if schedule_at.tzinfo is not None:
            # Normalise to local time — TikTok Studio always uses the
            # browser's local timezone for the date/time picker.
            schedule_at = schedule_at.astimezone().replace(tzinfo=None)

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
