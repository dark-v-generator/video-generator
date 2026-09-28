"""A history store over dicts and lists, meeting the same contract as SQLite."""

import dataclasses
from datetime import datetime, timezone
from typing import Optional

from src.entities.history import (
    Collection,
    PerformanceSnapshot,
    PublishAttempt,
    PublishedRecord,
    RedditSnapshot,
    RunMode,
    RunSummary,
    VideoRecord,
)
from src.storage import HistoryConflictError


def _utc(value: Optional[datetime]) -> Optional[datetime]:
    return value.astimezone(timezone.utc) if value else None


class InMemoryHistoryStore:
    def __init__(self):
        self.runs: dict[int, RunSummary] = {}
        self.records: dict[int, VideoRecord] = {}
        self.snapshots: dict[int, list[RedditSnapshot]] = {}
        self.attempts: dict[int, list[PublishAttempt]] = {}
        self.performance: dict[int, list[PerformanceSnapshot]] = {}
        self.collection_rows: list[Collection] = []

    def start_run(self, *, mode: RunMode, requested: int, started_at: datetime) -> int:
        run_id = len(self.runs) + 1
        self.runs[run_id] = RunSummary(
            id=run_id,
            started_at=_utc(started_at),
            finished_at=None,
            mode=mode,
            requested=requested,
            target=0,
            candidates_found=0,
            produced=0,
            scheduled=0,
            skipped={},
        )
        return run_id

    def finish_run(self, run_id: int, summary: RunSummary) -> None:
        if run_id not in self.runs:
            raise HistoryConflictError(f"No run {run_id} to finish")
        self.runs[run_id] = dataclasses.replace(
            summary,
            id=run_id,
            started_at=self.runs[run_id].started_at,
            finished_at=_utc(summary.finished_at),
            skipped=dict(summary.skipped),
        )

    def run_summary(self, run_id: int) -> RunSummary:
        return self.runs[run_id]

    def add_video_record(
        self, record: VideoRecord, discovery_signals: Optional[RedditSnapshot]
    ) -> int:
        record_id = len(self.records) + 1
        self.records[record_id] = dataclasses.replace(
            record,
            id=record_id,
            created_at=_utc(record.created_at),
            post_created_utc=_utc(record.post_created_utc),
            hashtags=list(record.hashtags),
            imported=record.imported or discovery_signals is None,
        )
        self.snapshots[record_id] = []
        self.attempts[record_id] = []
        if discovery_signals is not None:
            self.snapshots[record_id].append(
                dataclasses.replace(
                    discovery_signals, taken_at=_utc(discovery_signals.taken_at)
                )
            )
        return record_id

    def find_record_by_video_path(
        self, video_path: str, *, post_url: Optional[str] = None
    ) -> Optional[VideoRecord]:
        return next(
            (
                r
                for r in reversed(self.records.values())
                if r.video_path == video_path
                and (post_url is None or r.post_url == post_url)
            ),
            None,
        )

    def reddit_snapshots(self, record_id: int) -> list[RedditSnapshot]:
        return list(self.snapshots.get(record_id, []))

    def add_publish_attempt(self, record_id: int, attempt: PublishAttempt) -> None:
        if record_id not in self.records:
            raise HistoryConflictError(f"FOREIGN KEY: no record {record_id}")
        attempt = dataclasses.replace(
            attempt,
            attempted_at=_utc(attempt.attempted_at),
            scheduled_at=_utc(attempt.scheduled_at),
            hashtags=list(attempt.hashtags),
        )
        if any(
            a.attempted_at == attempt.attempted_at for a in self.attempts[record_id]
        ):
            raise HistoryConflictError(f"UNIQUE attempt: {record_id}")
        self.attempts[record_id].append(attempt)
        record = self.records[record_id]
        if not record.hashtags:
            self.records[record_id] = dataclasses.replace(
                record, hashtags=list(attempt.hashtags)
            )

    def publish_attempts(self, record_id: int) -> list[PublishAttempt]:
        return list(self.attempts.get(record_id, []))

    def video_record(self, record_id: int) -> VideoRecord:
        if record_id not in self.records:
            raise HistoryConflictError(f"No record {record_id}")
        return self.records[record_id]

    def published_records(self, since: datetime) -> list[PublishedRecord]:
        since = _utc(since)
        published = []
        for record_id, record in self.records.items():
            with_slot = [a for a in self.attempts[record_id] if a.scheduled_at]
            if record.tiktok_video_id or any(
                a.scheduled_at >= since for a in with_slot
            ):
                scheduled = [a for a in with_slot if a.status == "scheduled"]
                newest = (scheduled or with_slot or [None])[-1]
                published.append(
                    PublishedRecord(record, newest.scheduled_at if newest else None)
                )
        return published

    def record_collection(
        self,
        collection: Collection,
        performance: dict[int, PerformanceSnapshot],
        reddit: dict[int, RedditSnapshot],
    ) -> int:
        # Checked before anything is written, as the SQLite transaction would.
        for record_id in [*performance, *reddit]:
            if record_id not in self.records:
                raise HistoryConflictError(f"FOREIGN KEY: no record {record_id}")
        for record_id, snapshot in performance.items():
            self._check_video_id_free(record_id, snapshot.tiktok_video_id)
        self.collection_rows.append(
            dataclasses.replace(
                collection,
                started_at=_utc(collection.started_at),
                finished_at=_utc(collection.finished_at),
            )
        )
        for record_id, snapshot in performance.items():
            self.performance.setdefault(record_id, []).append(
                dataclasses.replace(
                    snapshot,
                    taken_at=_utc(snapshot.taken_at),
                    tiktok_created_at=_utc(snapshot.tiktok_created_at),
                )
            )
            self.records[record_id] = dataclasses.replace(
                self.records[record_id], tiktok_video_id=snapshot.tiktok_video_id
            )
        for record_id, snapshot in reddit.items():
            self.snapshots[record_id].append(
                dataclasses.replace(snapshot, taken_at=_utc(snapshot.taken_at))
            )
        return len(self.collection_rows)

    def assign_tiktok_video(self, record_id: int, tiktok_video_id: str) -> None:
        if record_id not in self.records:
            raise HistoryConflictError(f"No record {record_id}")
        self._check_video_id_free(record_id, tiktok_video_id)
        self.records[record_id] = dataclasses.replace(
            self.records[record_id], tiktok_video_id=tiktok_video_id
        )

    def _check_video_id_free(self, record_id: int, tiktok_video_id: str) -> None:
        if any(
            r.tiktok_video_id == tiktok_video_id
            for other_id, r in self.records.items()
            if other_id != record_id
        ):
            raise HistoryConflictError(f"UNIQUE tiktok_video_id: {tiktok_video_id}")

    def performance_snapshots(self, record_id: int) -> list[PerformanceSnapshot]:
        return list(self.performance.get(record_id, []))

    def collections(self) -> list[Collection]:
        return list(self.collection_rows)
