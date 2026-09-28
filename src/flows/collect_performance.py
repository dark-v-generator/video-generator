"""The performance collection: read the account's videos, find each one's
record, and keep what TikTok and Reddit say about it today.

Nothing is written until everything is read. A session that expired, a Studio
that changed or a Reddit that is down stops the collection with the cause and
leaves the history as it was (FR-014); what was read goes in one transaction.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from ..capabilities.discovery import StoryDiscovery
from ..capabilities.performance import PerformanceSource, match
from ..capabilities.publishing import strip_trailing_hashtags
from ..entities.configs.flows import CollectionConfig
from ..entities.history import (
    Collection,
    CollectionReport,
    PerformanceSnapshot,
    TikTokVideoStats,
)
from ..storage import HistoryStore
from .progress import Progress


@dataclass(kw_only=True)
class PerformanceCollection:
    source: PerformanceSource
    discovery: StoryDiscovery
    history: HistoryStore
    config: CollectionConfig
    progress: Progress
    now: Callable[[], datetime] = datetime.now

    async def collect(self, *, lookback_days: Optional[int] = None) -> CollectionReport:
        days = lookback_days or self.config.lookback_days
        # The Studio's dates are in UTC; a naive clock is local time.
        started_at = self.now().astimezone(timezone.utc)
        since = started_at - timedelta(days=days)
        try:
            videos = await self.source.fetch(since=since)
            published = self.history.published_records(since)
            await self.progress(
                f"🔎 {len(videos)} vídeos no Studio,"
                f" {len(published)} registros publicados"
            )
            result = match(
                published, videos, max_gap=timedelta(hours=self.config.max_gap_hours)
            )
            metrics = {
                record_id: await self.source.metrics(video.video_id)
                for record_id, video in result.matched.items()
            }
        finally:
            # The Studio shares the publisher's profile: free it before Reddit.
            await self.source.close()

        taken_at = self.now()
        performance = {
            record_id: PerformanceSnapshot(
                taken_at=taken_at,
                tiktok_video_id=video.video_id,
                metrics=metrics[record_id],
                tiktok_created_at=video.created_at,
            )
            for record_id, video in result.matched.items()
        }
        # The parts of a story share a post: read it once.
        post_urls = {
            p.record.id: p.record.post_url
            for p in published
            if p.record.id in result.matched
        }
        signals = {
            url: self.discovery.signals(url)
            for url in dict.fromkeys(post_urls.values())
        }
        reddit = {record_id: signals[url] for record_id, url in post_urls.items()}

        collection = Collection(
            started_at=started_at,
            finished_at=self.now(),
            lookback_days=days,
            matched=len(result.matched),
            unmatched=len(result.unmatched),
            ambiguous=len(result.ambiguous),
            reddit_refreshed=len(reddit),
        )
        self.history.record_collection(collection, performance, reddit)

        await self.progress(
            f"✅ {collection.matched} casados, {collection.unmatched} sem par,"
            f" {collection.ambiguous} ambíguos"
        )
        for video in result.unmatched:
            await self.progress(f"❓ Sem par: {_describe(video)}")
        for video, record_ids in result.ambiguous:
            candidates = ", ".join(str(record_id) for record_id in record_ids)
            await self.progress(
                f"⚠️ Ambíguo: {_describe(video)} — registros {candidates}"
            )
        return CollectionReport(
            collection=collection,
            unmatched_videos=result.unmatched,
            ambiguous=result.ambiguous,
        )

    def assign(self, tiktok_video_id: str, record_id: int) -> None:
        """The operator says which record a video is; the next collection
        matches it by id."""
        self.history.assign_tiktok_video(record_id, tiktok_video_id)


def _describe(video: TikTokVideoStats) -> str:
    caption = strip_trailing_hashtags(video.description)
    if len(caption) > 60:
        caption = caption[:60] + "…"
    posted = (
        video.created_at.astimezone().strftime("%d/%m %H:%M")
        if video.created_at
        else "?"
    )
    return f"{caption} ({posted}) — TikTok {video.video_id}"
