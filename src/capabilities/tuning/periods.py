"""What the channel did in a period, whatever the stories were: its reach
week by week and the uploads that never reached TikTok. Both explain a bad
month that no story finding would."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median
from typing import Optional

from ...entities.history import PublishAttempt
from .relative import Video


@dataclass(frozen=True)
class Week:
    week: date  # its Monday
    videos: int
    median_views: Optional[float]


@dataclass(frozen=True)
class LostUploads:
    attempts_failed: int
    never_published: int


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly_channel(videos: list[Video], since: date, until: date) -> list[Week]:
    """Every week from the one holding ``since`` to the one holding
    ``until``, by the local day each video went public; a week without
    videos is shown empty, since a gap is news too. The median is over the
    videos already collected, settled or not."""
    published = defaultdict(list)
    for video in videos:
        if video.published_at is not None:
            published[_monday(video.published_at.astimezone().date())].append(video)
    weeks = []
    monday = _monday(since)
    while monday <= until:
        views = [v.views for v in published[monday] if v.views is not None]
        weeks.append(
            Week(
                week=monday,
                videos=len(published[monday]),
                median_views=median(views) if views else None,
            )
        )
        monday += timedelta(days=7)
    return weeks


def lost_uploads(
    videos: list[Video], attempts: dict[int, list[PublishAttempt]]
) -> LostUploads:
    """The failed publish attempts of these videos, and the videos that never
    went public: no scheduled attempt and nothing on TikTok."""
    return LostUploads(
        attempts_failed=sum(
            1
            for video in videos
            for attempt in attempts.get(video.record_id, [])
            if attempt.status == "failed"
        ),
        never_published=sum(1 for v in videos if v.published_at is None),
    )
