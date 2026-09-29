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
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlparse

from patchright.async_api import BrowserContext, Error, Page, Response
from patchright.async_api import async_playwright

from src.core.logging_config import get_logger
from src.entities.history import PerformanceMetrics, TikTokVideoStats
from src.proxies.interfaces import (
    ITikTokStudioProxy,
    TikTokSessionExpiredError,
    TikTokStudioLayoutError,
)
from src.proxies.tiktok_browser import DEFAULT_USER_AGENT, STEALTH_BROWSER_ARGS

STUDIO_ORIGIN = "https://www.tiktok.com"
CONTENT_LIST_URL = f"{STUDIO_ORIGIN}/tiktokstudio/content"
ANALYTICS_URL_TEMPLATE = f"{STUDIO_ORIGIN}/tiktokstudio/analytics/{{video_id}}"

# The responses the pages above fetch (see scripts/tiktok_studio_probe.py and
# research.md §2). The content list POSTs item_list once per 50/10 posts as it
# scrolls; the analytics page GETs insight several times, and only one of
# those answers carries the retention numbers.
ITEM_LIST_PATH = "/tiktok/creator/manage/item_list/v1/"
INSIGHT_PATH = "/aweme/v2/data/insight/"
# Scrolls in a row that bring no post we had not seen before.
MAX_STALLED_SCROLLS = 3

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


class PatchrightTikTokStudioProxy(ITikTokStudioProxy):
    """Reads the Studio's own JSON through the publisher's browser profile."""

    def __init__(
        self,
        user_data_dir: Path,
        headless: bool = False,
        page_timeout_seconds: int = 60,
    ) -> None:
        self._user_data_dir = user_data_dir
        self._headless = headless
        self._timeout = page_timeout_seconds
        self._stack: Optional[AsyncExitStack] = None
        self._page: Optional[Page] = None
        self._bodies: dict[str, list[dict]] = {ITEM_LIST_PATH: [], INSIGHT_PATH: []}

    async def list_videos(self, *, since: datetime) -> list[TikTokVideoStats]:
        page = await self._open()
        self._bodies[ITEM_LIST_PATH].clear()
        await page.goto(CONTENT_LIST_URL, wait_until="domcontentloaded")
        seen, known, stalled = 0, 0, 0
        while True:
            bodies = await self._wait_for_more(ITEM_LIST_PATH, seen, "the content list")
            seen = len(bodies)
            videos, covered, loaded = _videos_since(bodies, since)
            if covered:
                return videos
            stalled = stalled + 1 if loaded == known else 0
            if stalled >= MAX_STALLED_SCROLLS:
                raise TikTokStudioLayoutError(
                    f"{ITEM_LIST_PATH} still has_more after {loaded} posts, "
                    f"but {stalled} scrolls loaded no older post"
                )
            known = loaded
            await _scroll(page)

    async def video_analytics(self, video_id: str) -> PerformanceMetrics:
        page = await self._open()
        self._bodies[INSIGHT_PATH].clear()
        await page.goto(
            ANALYTICS_URL_TEMPLATE.format(video_id=video_id),
            wait_until="domcontentloaded",
        )
        seen = 0
        while True:
            bodies = await self._wait_for_more(
                INSIGHT_PATH, seen, f"the retention of video {video_id}"
            )
            seen = len(bodies)
            body = _retention_response(bodies, video_id)
            if body is not None:
                return _parse_analytics(body)

    async def close(self) -> None:
        stack, self._stack, self._page = self._stack, None, None
        if stack is not None:
            await stack.aclose()

    async def _open(self) -> Page:
        if self._page is None:
            stack = AsyncExitStack()
            page = await stack.enter_async_context(
                studio_page(
                    self._user_data_dir,
                    headless=self._headless,
                    page_timeout_seconds=self._timeout,
                )
            )
            page.on("response", self._on_response)
            self._stack, self._page = stack, page
        return self._page

    async def _on_response(self, response: Response) -> None:
        path = urlparse(response.url).path
        if path not in self._bodies or not response.ok:
            return
        try:
            body = await response.json()
        except Error:
            # The page navigated away before the body was read; the wait
            # below fails with the endpoint's name if nothing else arrives.
            return
        self._bodies[path].append(body)

    async def _wait_for_more(self, path: str, seen: int, what: str) -> list[dict]:
        """Every body of ``path`` so far, once there are more than ``seen``."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout
        while len(self._bodies[path]) <= seen:
            raise_if_logged_out(self._page)
            if loop.time() > deadline:
                raise TikTokStudioLayoutError(
                    f"no {path} response for {what} within {self._timeout}s"
                )
            await asyncio.sleep(0.5)
        return list(self._bodies[path])


async def _scroll(page: Page) -> None:
    # The content table may scroll inside its own container, so wheel over
    # the middle of the page as well as scrolling the document.
    width, height = await page.evaluate("[window.innerWidth, window.innerHeight]")
    await page.mouse.move(width / 2, height / 2)
    await page.mouse.wheel(0, 4000)
    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")


def _videos_since(
    bodies: list[dict], since: datetime
) -> tuple[list[TikTokVideoStats], bool, int]:
    """The posts from ``since`` on, newest first; whether the pages loaded so
    far reach back to ``since``; and how many distinct posts they hold.

    The Studio refetches the first page while scrolling, so a post seen twice
    keeps its latest numbers. A pinned post sits on top whatever its age and
    says nothing about how far back the list goes.
    """
    videos: dict[str, TikTokVideoStats] = {}
    pinned: set[str] = set()
    covered = False
    for body in bodies:
        for item in _field(body, "item_list", ITEM_LIST_PATH):
            video = _parse_item(item)
            videos[video.video_id] = video
            if _field(item, "is_pinned", ITEM_LIST_PATH):
                pinned.add(video.video_id)
        if not _field(body, "has_more", ITEM_LIST_PATH):
            covered = True
    covered = covered or any(
        video.created_at < since
        for video in videos.values()
        if video.video_id not in pinned
    )
    recent = [video for video in videos.values() if video.created_at >= since]
    recent.sort(key=lambda video: video.created_at, reverse=True)
    return recent, covered, len(videos)


def _parse_video_list(body: dict) -> list[TikTokVideoStats]:
    """One page of the content list, as the Studio sent it."""
    return [_parse_item(item) for item in _field(body, "item_list", ITEM_LIST_PATH)]


def _parse_item(item: dict) -> TikTokVideoStats:
    # post_time is when the post went public: the scheduled slot for a
    # scheduled post (create_time is the upload).
    return TikTokVideoStats(
        video_id=str(_field(item, "item_id", ITEM_LIST_PATH)),
        description=_field(item, "desc", ITEM_LIST_PATH),
        created_at=datetime.fromtimestamp(
            int(_field(item, "post_time", ITEM_LIST_PATH)), tz=timezone.utc
        ),
        metrics=PerformanceMetrics(
            views=int(_field(item, "play_count", ITEM_LIST_PATH)),
            likes=int(_field(item, "like_count", ITEM_LIST_PATH)),
            comments=int(_field(item, "comment_count", ITEM_LIST_PATH)),
            shares=int(_field(item, "share_count", ITEM_LIST_PATH)),
            saves=int(_field(item, "favorite_count", ITEM_LIST_PATH)),
        ),
    )


def _retention_response(bodies: list[dict], video_id: str) -> Optional[dict]:
    """The insight answer that carries this video's retention, if it came."""
    for body in bodies:
        info = body.get("video_info") or {}
        if (
            str(info.get("aweme_id")) == video_id
            and body.get("video_finish_rate_realtime") is not None
        ):
            return body
    return None


def _parse_analytics(body: dict) -> PerformanceMetrics:
    """A video's counts and retention from the analytics page's insight."""
    info = _field(body, "video_info", INSIGHT_PATH)
    stats = _field(info, "statistics", INSIGHT_PATH, "video_info.statistics")
    return PerformanceMetrics(
        views=int(_field(stats, "play_count", INSIGHT_PATH)),
        likes=int(_field(stats, "digg_count", INSIGHT_PATH)),
        comments=int(_field(stats, "comment_count", INSIGHT_PATH)),
        shares=int(_field(stats, "share_count", INSIGHT_PATH)),
        saves=int(_field(stats, "collect_count", INSIGHT_PATH)),
        avg_watch_seconds=_insight(body, "video_per_duration_realtime"),
        full_watch_ratio=_insight(body, "video_finish_rate_realtime"),
        new_followers=_new_followers(body),
        retention=_retention_curve(body),
        traffic_sources=_traffic_sources(body),
    )


def _insight_value(body: dict, name: str) -> Optional[dict]:
    """An insight's value object; None when the Studio says it has none (a
    status other than 0, as for a post too new to have retention)."""
    value = _field(_field(body, name, INSIGHT_PATH), "value", INSIGHT_PATH, name)
    if value.get("status") != 0:
        return None
    return value


def _insight(body: dict, name: str) -> Optional[float]:
    value = _insight_value(body, name)
    if value is None:
        return None
    return float(_field(value, "value", INSIGHT_PATH, f"{name}.value"))


def _new_followers(body: dict) -> Optional[int]:
    # Unlike the realtime insights, this one is the status and value itself.
    name = "video_new_followers"
    insight = _field(body, name, INSIGHT_PATH)
    if insight.get("status") != 0:
        return None
    return int(_field(insight, "value", INSIGHT_PATH, f"{name}.value"))


def _retention_curve(body: dict) -> Optional[tuple[float, ...]]:
    """The share still watching at each second, from the curve the Studio
    draws: one point per 1000 ms from 0. Other steps are a changed layout."""
    name = "video_retention_rate_realtime"
    value = _insight_value(body, name)
    if value is None:
        return None
    points = _field(value, "list", INSIGHT_PATH, f"{name}.list")
    for second, point in enumerate(points):
        timestamp = int(_field(point, "timestamp", INSIGHT_PATH, f"{name}.timestamp"))
        if timestamp != second * 1000:
            raise TikTokStudioLayoutError(
                f"{name} point {second} is at {timestamp} ms, not {second * 1000}"
                f" in {INSIGHT_PATH}"
            )
    return tuple(
        float(_field(point, "value", INSIGHT_PATH, f"{name}.value")) for point in points
    )


def _traffic_sources(body: dict) -> Optional[dict[str, float]]:
    name = "video_traffic_source_percent_realtime"
    value = _insight_value(body, name)
    if value is None:
        return None
    return {
        _field(source, "key", INSIGHT_PATH, f"{name}.key"): float(
            _field(source, "value", INSIGHT_PATH, f"{name}.value")
        )
        for source in _field(value, "value", INSIGHT_PATH, f"{name}.value")
    }


def _field(obj: dict, key: str, endpoint: str, label: Optional[str] = None) -> Any:
    if obj.get("status_code") not in (None, 0):
        raise TikTokStudioLayoutError(
            f"{endpoint} answered status_code {obj['status_code']}: "
            f"{obj.get('status_msg', '')}"
        )
    if obj.get(key) is None:
        raise TikTokStudioLayoutError(f"missing {label or key} in {endpoint}")
    return obj[key]
