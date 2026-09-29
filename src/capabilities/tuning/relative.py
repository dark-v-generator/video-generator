"""How a video did against what the channel published around it.

The channel's reach moves week to week (in September the median fell from
1 065 views to 430), so raw views compare a video with its week as much as
with its story. Dividing by the median of the videos published around it
cancels the week out; the median, not the mean, keeps one viral neighbour
from deciding it.
"""

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from statistics import median
from typing import Iterable, Optional

from ...entities.history import CrossedRow, PublishAttempt

NEIGHBOURS_EACH_SIDE = 5
# Fewer neighbours than this and the median is one or two videos' luck.
MINIMUM_NEIGHBOURS = 5


@dataclass(frozen=True)
class Video:
    """A video as the tuning report reads it."""

    row: CrossedRow
    # When it went public; None for a video that never did.
    published_at: Optional[datetime]
    # Its numbers were read long enough after it went public to be final.
    settled: bool
    relative: Optional[float] = None
    neighbours: int = 0
    # None on videos made before the history recorded them: a video with no
    # goal was made for the base, and one with no cycle is placed by date.
    goal: Optional[str] = None
    cycle: Optional[int] = None

    @property
    def record_id(self) -> int:
        return self.row.record.id

    @property
    def views(self) -> Optional[int]:
        performance = self.row.latest_performance
        return performance.metrics.views if performance else None

    @property
    def made_on(self) -> date:
        """The local day it was made, the day the operator reads it under."""
        return self.row.record.created_at.astimezone().date()

    @property
    def is_base(self) -> bool:
        return self.goal in (None, "base")


def published_at(
    row: CrossedRow, attempts: Iterable[PublishAttempt]
) -> Optional[datetime]:
    """The slot of the newest scheduled attempt. The publisher sometimes
    reports a failure for a video TikTok did post: then TikTok's own date."""
    slots = [a.scheduled_at for a in attempts if a.status == "scheduled"]
    if slots and slots[-1] is not None:
        return slots[-1]
    performance = row.latest_performance
    return performance.tiktok_created_at if performance else None


def settled(
    published: Optional[datetime], data_as_of: Optional[datetime], settle_days: int
) -> bool:
    """Whether the numbers read at ``data_as_of`` are final. Counted to when
    they were read, not to today: a video collected on its third day keeps
    its third-day views however old it gets."""
    if published is None or data_as_of is None:
        return False
    return data_as_of - published >= timedelta(days=settle_days)


def measure(
    rows: list[CrossedRow],
    attempts: dict[int, list[PublishAttempt]],
    settle_days: int = 7,
) -> list[Video]:
    """Every row as a video, in the rows' order, with its relative
    performance when it is settled."""
    videos = []
    for row in rows:
        published = published_at(row, attempts.get(row.record.id, []))
        performance = row.latest_performance
        readable = performance is not None and performance.metrics.views is not None
        videos.append(
            Video(
                row=row,
                published_at=published,
                settled=readable
                and settled(published, performance.taken_at, settle_days),
                goal=row.record.goal,
                cycle=row.record.cycle,
            )
        )
    return relative_performance(videos)


def relative_performance(videos: list[Video]) -> list[Video]:
    """Each settled video's views over the median of its ten nearest settled
    neighbours in publishing order: five on each side, or more on one side
    where the other runs out. The video itself is never among them; an
    unsettled one has no relative and is no one's neighbour."""
    peers = sorted(
        (v for v in videos if v.settled), key=lambda v: (v.published_at, v.record_id)
    )
    position = {v.record_id: i for i, v in enumerate(peers)}
    total = 2 * NEIGHBOURS_EACH_SIDE
    measured = []
    for video in videos:
        if video.record_id not in position:
            measured.append(video)
            continue
        i = position[video.record_id]
        before = min(NEIGHBOURS_EACH_SIDE, i)
        after = min(NEIGHBOURS_EACH_SIDE, len(peers) - 1 - i)
        if before < NEIGHBOURS_EACH_SIDE:
            after = min(len(peers) - 1 - i, total - before)
        if after < NEIGHBOURS_EACH_SIDE:
            before = min(i, total - after)
        neighbours = peers[i - before : i] + peers[i + 1 : i + 1 + after]
        typical = median(n.views for n in neighbours) if neighbours else 0
        relative = (
            video.views / typical
            if len(neighbours) >= MINIMUM_NEIGHBOURS and typical > 0
            else None
        )
        measured.append(replace(video, relative=relative, neighbours=len(neighbours)))
    return measured
