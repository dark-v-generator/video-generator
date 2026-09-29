"""What the performance history keeps: one record per video, its publish
attempts, one summary per run, and what each collection read from TikTok.

Every write that fails raises. Unlike the publish log, the history is the
product: a run whose videos are not recorded went wrong.
"""

from datetime import date, datetime
from typing import Iterable, Optional, Protocol

from ..entities.history import (
    CROSSED_COLUMNS,
    Collection,
    CrossedRow,
    GoalCounts,
    PerformanceSnapshot,
    PublishAttempt,
    PublishedRecord,
    RedditSnapshot,
    RunMode,
    RunSummary,
    VideoRecord,
)


class HistoryError(Exception):
    """The history could not be written. The run stops: it is the product."""


class HistoryConflictError(HistoryError):
    """A write clashed with what is already recorded: a publish attempt or
    a TikTok video id recorded twice, or a record that does not exist."""


class UnknownColumnError(ValueError):
    """A sort or filter named a column the crossed view does not have."""


def check_crossed_columns(names: Iterable[str]) -> None:
    """Refuse any name outside CROSSED_COLUMNS before it gets near a query."""
    unknown = [name for name in names if name not in CROSSED_COLUMNS]
    if unknown:
        raise UnknownColumnError(
            f"Unknown column {', '.join(unknown)}. "
            f"Valid columns: {', '.join(CROSSED_COLUMNS)}"
        )


class HistoryStore(Protocol):
    def start_run(self, *, mode: RunMode, requested: int, started_at: datetime) -> int:
        """Open the run's summary with zero counts; a run that dies midway
        leaves it without ``finished_at``."""
        ...

    def finish_run(self, run_id: int, summary: RunSummary) -> None: ...

    def run_summary(self, run_id: int) -> RunSummary: ...

    def add_video_record(
        self, record: VideoRecord, discovery_signals: Optional[RedditSnapshot]
    ) -> int:
        """Record a video and the post's numbers when it was found.

        None is for a video that was not found by this run (imported, or a
        manifest from before the history); it is stored as ``imported``.
        """
        ...

    def find_record_by_video_path(
        self, video_path: str, *, post_url: Optional[str] = None
    ) -> Optional[VideoRecord]:
        """The newest record for the path: each daily run reuses the paths of
        the one before, so older records keep the path of a file now gone.
        With *post_url*, the newest one made from that post."""
        ...

    def goal_counts(self, since: date) -> GoalCounts:
        """The records runs made from local midnight of *since* on, imported
        ones left out, and how many had an experiment as their goal."""
        ...

    def reddit_snapshots(self, record_id: int) -> list[RedditSnapshot]: ...

    def add_publish_attempt(self, record_id: int, attempt: PublishAttempt) -> None: ...

    def publish_attempts(self, record_id: int) -> list[PublishAttempt]: ...

    def video_record(self, record_id: int) -> VideoRecord: ...

    def published_records(self, since: datetime) -> list[PublishedRecord]:
        """What a collection can match: the records with an attempt for a slot
        at or after ``since``, plus every record that already knows its TikTok
        video so it keeps gaining snapshots.

        A failed attempt counts: the publisher sometimes reports a failure for
        a video TikTok did schedule. The slot is the newest scheduled
        attempt's, or else the newest attempt's."""
        ...

    def record_collection(
        self,
        collection: Collection,
        performance: dict[int, PerformanceSnapshot],
        reddit: dict[int, RedditSnapshot],
    ) -> int:
        """Write a collection in one transaction: its row, a performance and a
        Reddit snapshot per record id, and each record's TikTok video id (the
        one its snapshot was read from). Any write that fails leaves nothing."""
        ...

    def assign_tiktok_video(self, record_id: int, tiktok_video_id: str) -> None:
        """The operator's word on which video a record is; later collections
        match it by id."""
        ...

    def performance_snapshots(self, record_id: int) -> list[PerformanceSnapshot]: ...

    def collections(self) -> list[Collection]: ...

    def crossed_view(
        self,
        *,
        since: Optional[datetime] = None,
        filters: Optional[dict[str, str]] = None,
        sort: Optional[tuple[str, bool]] = None,
    ) -> list[CrossedRow]:
        """One row per record created at or after *since*, whether or not it
        has TikTok numbers yet.

        *filters* keeps the rows whose column equals the text given (as a
        number when both are numbers); *sort* is ``(column, descending)``, with
        empty values last either way and ties by record id. Any name outside
        CROSSED_COLUMNS raises UnknownColumnError listing the valid ones."""
        ...
