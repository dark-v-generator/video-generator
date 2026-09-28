"""Where a collection reads the account's numbers from.

The Studio reader is one source; an export file or an official interface
would be another, and the collection would not change (FR-020).
"""

from datetime import datetime
from typing import Protocol

from ...entities.history import PerformanceMetrics, TikTokVideoStats
from ...proxies.interfaces import ITikTokStudioProxy


class PerformanceSource(Protocol):
    async def fetch(self, *, since: datetime) -> list[TikTokVideoStats]:
        """The account's videos made public at or after ``since``."""
        ...

    async def metrics(self, video_id: str) -> PerformanceMetrics:
        """One video's numbers, retention included when the source has it."""
        ...

    async def close(self) -> None:
        """Release what the reads held (the Studio's browser profile)."""
        ...


class StudioPerformanceSource:
    """The TikTok Studio, read with the server's session."""

    def __init__(self, proxy: ITikTokStudioProxy):
        self._proxy = proxy

    async def fetch(self, *, since: datetime) -> list[TikTokVideoStats]:
        return await self._proxy.list_videos(since=since)

    async def metrics(self, video_id: str) -> PerformanceMetrics:
        return await self._proxy.video_analytics(video_id)

    async def close(self) -> None:
        await self._proxy.close()
