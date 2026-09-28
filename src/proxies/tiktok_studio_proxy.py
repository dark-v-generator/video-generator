"""Reads the account's numbers from the TikTok Studio, without an agent.

The reader opens the publisher's Chromium profile with patchright, so it
rides the session the publisher keeps alive, and it never scrapes the page:
it listens to the JSON the Studio fetches to draw itself. Which responses
matter, and which fields they carry, was fixed by running
``scripts/tiktok_studio_probe.py`` on the server; when the Studio changes,
rerun the probe and adjust the parser to the new dump.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator
from urllib.parse import urlparse

from patchright.async_api import BrowserContext, Page, async_playwright

from src.core.logging_config import get_logger
from src.proxies.interfaces import TikTokSessionExpiredError
from src.proxies.tiktok_browser import DEFAULT_USER_AGENT, STEALTH_BROWSER_ARGS

STUDIO_ORIGIN = "https://www.tiktok.com"
CONTENT_LIST_URL = f"{STUDIO_ORIGIN}/tiktokstudio/content"
ANALYTICS_URL_TEMPLATE = f"{STUDIO_ORIGIN}/tiktokstudio/analytics/{{video_id}}"

# Same budget the publisher gives Chromium to flush the profile on stop.
CLOSE_TIMEOUT_SECONDS = 15.0


@asynccontextmanager
async def studio_page(
    user_data_dir: Path, *, headless: bool, page_timeout_seconds: int
) -> AsyncIterator[Page]:
    """A page in the publisher's profile.

    Uses the installed Chrome, the same binary the publisher drives, so the
    profile is never opened by an older Chromium than the one that wrote it.
    A profile already open in another Chrome fails here, before any page.

    No playwright-stealth script, unlike the publisher: patchright hides the
    automation itself, and its init-script injection made every navigation
    fail with ERR_NAME_NOT_RESOLVED on the server.
    """
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            str(user_data_dir),
            channel="chrome",
            headless=headless,
            args=STEALTH_BROWSER_ARGS,
            user_agent=DEFAULT_USER_AGENT,
            no_viewport=True,
        )
        try:
            page = context.pages[0] if context.pages else await context.new_page()
            page.set_default_timeout(page_timeout_seconds * 1000)
            yield page
        finally:
            await _close(context)


def raise_if_logged_out(page: Page) -> None:
    """The Studio sends a logged-out profile to the login page."""
    if urlparse(page.url).path.startswith("/login"):
        raise TikTokSessionExpiredError(
            f"TikTok session expired: the Studio redirected to {page.url}. "
            "Log in again with `just prod-tiktok-bootstrap-vnc`."
        )


async def _close(context: BrowserContext) -> None:
    # Closing is what writes the session back to the profile; a hung close
    # must not hold the run, and the next launch will notice a broken profile.
    try:
        await asyncio.wait_for(context.close(), timeout=CLOSE_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        get_logger(__name__).warning(
            "Chromium did not close within %.0fs; the profile may not have "
            "been flushed",
            CLOSE_TIMEOUT_SECONDS,
        )
