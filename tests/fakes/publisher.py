"""Fake TikTok publisher that records every call and can fail on chosen ones."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Set

from src.proxies.interfaces import ITikTokPublisherProxy


@dataclass
class PublishCall:
    video_path: str
    description: str
    hashtags: List[str]
    schedule_at: Optional[datetime]


class FakePublisher(ITikTokPublisherProxy):
    """``fail_on`` holds 1-based call numbers that raise instead of publishing."""

    def __init__(self, fail_on: Optional[Set[int]] = None):
        self._fail_on = fail_on or set()
        self.calls: List[PublishCall] = []

    async def publish_video(
        self,
        video_path: str,
        description: str,
        hashtags: Optional[List[str]] = None,
        schedule_at: Optional[datetime] = None,
    ) -> str:
        self.calls.append(
            PublishCall(video_path, description, list(hashtags or []), schedule_at)
        )
        number = len(self.calls)
        if number in self._fail_on:
            raise RuntimeError(f"publisher failed on call {number}")
        return f"https://www.tiktok.com/@fake/video/{number}"
