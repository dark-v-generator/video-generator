"""A performance source with fixed videos and metrics, and failures on demand."""

from datetime import datetime
from typing import Optional

from src.entities.history import PerformanceMetrics, TikTokVideoStats
from src.proxies.interfaces import TikTokSessionExpiredError, TikTokStudioLayoutError


class FakePerformanceSource:
    def __init__(
        self,
        videos: list[TikTokVideoStats],
        metrics_by_id: dict[str, PerformanceMetrics],
        fail_fetch: bool = False,
        fail_metrics_for: Optional[set[str]] = None,
    ):
        self.videos = videos
        self.metrics_by_id = metrics_by_id
        self.fail_fetch = fail_fetch
        self.fail_metrics_for = fail_metrics_for or set()
        self.since: list[datetime] = []
        self.asked: list[str] = []
        self.closed = 0

    async def fetch(self, *, since: datetime) -> list[TikTokVideoStats]:
        self.since.append(since)
        if self.fail_fetch:
            raise TikTokSessionExpiredError("The Studio sent us to the login page")
        return [v for v in self.videos if v.created_at >= since]

    async def metrics(self, video_id: str) -> PerformanceMetrics:
        self.asked.append(video_id)
        if video_id in self.fail_metrics_for:
            raise TikTokStudioLayoutError(f"video_info em insight ({video_id})")
        return self.metrics_by_id[video_id]

    async def close(self) -> None:
        self.closed += 1
