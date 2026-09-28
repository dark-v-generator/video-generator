"""A history store over dicts and lists, meeting the same contract as SQLite."""

import dataclasses
from datetime import datetime, timezone
from typing import Optional

from src.entities.history import (
    PublishAttempt,
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
        if self.find_record_by_video_path(record.video_path):
            raise HistoryConflictError(f"UNIQUE video_path: {record.video_path}")
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

    def find_record_by_video_path(self, video_path: str) -> Optional[VideoRecord]:
        return next(
            (r for r in self.records.values() if r.video_path == video_path), None
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
