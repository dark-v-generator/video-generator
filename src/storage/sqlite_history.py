"""The history the server keeps: a single SQLite file, one transaction per write.

Dates are stored as ISO 8601 text in UTC; a naive datetime is taken as local
time, which is what ``datetime.now()`` gives the run.
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from ..entities.history import (
    ModelGrade,
    ProductionRecipe,
    PublishAttempt,
    RedditSnapshot,
    RunMode,
    RunSummary,
    VideoRecord,
)
from .history_contract import HistoryConflictError, HistoryError

# The daily run writes to the same output/daily/story_NN.mp4 every day, so a
# path names a video only until the next run: it is not unique.
_VIDEO_RECORDS_COLUMNS = """
  id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, run_id INTEGER,
  video_path TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '',
  post_url TEXT NOT NULL, community TEXT, author TEXT, post_created_utc TEXT,
  part_index INTEGER NOT NULL DEFAULT 1, part_count INTEGER NOT NULL DEFAULT 1,
  language TEXT, duration_seconds REAL,
  grade_overall REAL, grade_verdict TEXT, grade_retention REAL, grade_quality REAL,
  grade_virality REAL, grade_tiktok_fit REAL, grade_hook REAL, deterministic_score REAL,
  story_prompt_version TEXT, grading_prompt_version TEXT, writer_model TEXT, grader_model TEXT,
  rendering_strategy TEXT, speech_provider TEXT, speech_rate REAL, narrator_gender TEXT,
  voice_id TEXT, hashtags TEXT NOT NULL DEFAULT '', tiktok_video_id TEXT UNIQUE,
  imported INTEGER NOT NULL DEFAULT 0"""

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS run_summaries (
  id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
  mode TEXT NOT NULL, requested INTEGER, target INTEGER, candidates_found INTEGER,
  produced INTEGER, scheduled INTEGER, skipped_json TEXT NOT NULL,
  stopped_reason TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS video_records ({_VIDEO_RECORDS_COLUMNS});
CREATE INDEX IF NOT EXISTS video_records_by_path ON video_records (video_path);
CREATE TABLE IF NOT EXISTS reddit_snapshots (
  id INTEGER PRIMARY KEY, record_id INTEGER NOT NULL REFERENCES video_records(id),
  taken_at TEXT NOT NULL, source TEXT NOT NULL, score INTEGER, num_comments INTEGER,
  upvote_ratio REAL, available INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS publish_attempts (
  id INTEGER PRIMARY KEY, record_id INTEGER NOT NULL REFERENCES video_records(id),
  attempted_at TEXT NOT NULL, status TEXT NOT NULL, scheduled_at TEXT,
  hashtags TEXT NOT NULL DEFAULT '', publish_result TEXT NOT NULL DEFAULT '',
  error TEXT NOT NULL DEFAULT '', UNIQUE(record_id, attempted_at));
CREATE TABLE IF NOT EXISTS collections (
  id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT NOT NULL,
  lookback_days INTEGER, matched INTEGER, unmatched INTEGER, ambiguous INTEGER,
  reddit_refreshed INTEGER);
CREATE TABLE IF NOT EXISTS performance_snapshots (
  id INTEGER PRIMARY KEY, record_id INTEGER NOT NULL REFERENCES video_records(id),
  collection_id INTEGER NOT NULL REFERENCES collections(id), taken_at TEXT NOT NULL,
  tiktok_video_id TEXT NOT NULL, views INTEGER, likes INTEGER, comments INTEGER,
  shares INTEGER, saves INTEGER, avg_watch_seconds REAL, full_watch_ratio REAL,
  tiktok_created_at TEXT);
"""

_GRADE_FIELDS = ["retention", "quality", "virality", "tiktok_fit", "hook"]
_RECIPE_FIELDS = [
    "story_prompt_version",
    "grading_prompt_version",
    "writer_model",
    "grader_model",
    "rendering_strategy",
    "speech_provider",
    "speech_rate",
    "narrator_gender",
    "voice_id",
]


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    return value.astimezone(timezone.utc).isoformat() if value else None


def _from_iso(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _tags_text(tags: list[str]) -> str:
    return " ".join(f"#{tag}" for tag in tags)


def _tags_list(text: str) -> list[str]:
    return [tag.lstrip("#") for tag in text.split()]


class SqliteHistoryStore:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._allow_reused_video_paths()

    def _allow_reused_video_paths(self) -> None:
        """A history created when video_path was UNIQUE is rebuilt once
        without it, keeping every row and id."""
        unique_on_path = any(
            index["unique"]
            and [
                column["name"]
                for column in self._conn.execute(
                    f"PRAGMA index_info('{index['name']}')"
                )
            ]
            == ["video_path"]
            for index in self._conn.execute("PRAGMA index_list(video_records)")
        )
        if not unique_on_path:
            return
        self._conn.executescript(f"""
            PRAGMA foreign_keys=OFF;
            BEGIN;
            CREATE TABLE video_records_rebuilt ({_VIDEO_RECORDS_COLUMNS});
            INSERT INTO video_records_rebuilt SELECT * FROM video_records;
            DROP TABLE video_records;
            ALTER TABLE video_records_rebuilt RENAME TO video_records;
            CREATE INDEX video_records_by_path ON video_records (video_path);
            COMMIT;
            PRAGMA foreign_keys=ON;
            """)

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        try:
            with self._conn:
                yield self._conn
        except sqlite3.IntegrityError as e:
            raise HistoryConflictError(str(e)) from e
        except sqlite3.Error as e:
            raise HistoryError(str(e)) from e

    def start_run(self, *, mode: RunMode, requested: int, started_at: datetime) -> int:
        with self._tx() as db:
            cursor = db.execute(
                "INSERT INTO run_summaries (started_at, mode, requested, target,"
                " candidates_found, produced, scheduled, skipped_json)"
                " VALUES (?, ?, ?, 0, 0, 0, 0, '{}')",
                (_to_iso(started_at), mode, requested),
            )
            return cursor.lastrowid

    def finish_run(self, run_id: int, summary: RunSummary) -> None:
        with self._tx() as db:
            cursor = db.execute(
                "UPDATE run_summaries SET finished_at = ?, requested = ?, target = ?,"
                " candidates_found = ?, produced = ?, scheduled = ?, skipped_json = ?,"
                " stopped_reason = ? WHERE id = ?",
                (
                    _to_iso(summary.finished_at),
                    summary.requested,
                    summary.target,
                    summary.candidates_found,
                    summary.produced,
                    summary.scheduled,
                    json.dumps(summary.skipped, sort_keys=True),
                    summary.stopped_reason,
                    run_id,
                ),
            )
            if cursor.rowcount != 1:
                raise HistoryConflictError(f"No run {run_id} to finish")

    def run_summary(self, run_id: int) -> RunSummary:
        row = self._conn.execute(
            "SELECT * FROM run_summaries WHERE id = ?", (run_id,)
        ).fetchone()
        return RunSummary(
            id=row["id"],
            started_at=_from_iso(row["started_at"]),
            finished_at=_from_iso(row["finished_at"]),
            mode=row["mode"],
            requested=row["requested"],
            target=row["target"],
            candidates_found=row["candidates_found"],
            produced=row["produced"],
            scheduled=row["scheduled"],
            skipped=json.loads(row["skipped_json"]),
            stopped_reason=row["stopped_reason"],
        )

    def add_video_record(
        self, record: VideoRecord, discovery_signals: Optional[RedditSnapshot]
    ) -> int:
        grade = record.grade
        recipe = record.recipe
        columns = {
            "created_at": _to_iso(record.created_at),
            "run_id": record.run_id,
            "video_path": record.video_path,
            "title": record.title,
            "summary": record.summary,
            "post_url": record.post_url,
            "community": record.community,
            "author": record.author,
            "post_created_utc": _to_iso(record.post_created_utc),
            "part_index": record.part_index,
            "part_count": record.part_count,
            "language": record.language,
            "duration_seconds": record.duration_seconds,
            "grade_overall": grade.overall if grade else None,
            "grade_verdict": grade.verdict if grade else None,
            **{
                f"grade_{f}": getattr(grade, f) if grade else None
                for f in _GRADE_FIELDS
            },
            "deterministic_score": record.deterministic_score,
            **{f: getattr(recipe, f) if recipe else None for f in _RECIPE_FIELDS},
            "hashtags": _tags_text(record.hashtags),
            "tiktok_video_id": record.tiktok_video_id,
            "imported": int(record.imported or discovery_signals is None),
        }
        with self._tx() as db:
            cursor = db.execute(
                f"INSERT INTO video_records ({', '.join(columns)})"
                f" VALUES ({', '.join('?' for _ in columns)})",
                list(columns.values()),
            )
            record_id = cursor.lastrowid
            if discovery_signals is not None:
                self._insert_reddit_snapshot(db, record_id, discovery_signals)
            return record_id

    @staticmethod
    def _insert_reddit_snapshot(
        db: sqlite3.Connection, record_id: int, snapshot: RedditSnapshot
    ) -> None:
        db.execute(
            "INSERT INTO reddit_snapshots (record_id, taken_at, source, score,"
            " num_comments, upvote_ratio, available) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                record_id,
                _to_iso(snapshot.taken_at),
                snapshot.source,
                snapshot.score,
                snapshot.num_comments,
                snapshot.upvote_ratio,
                int(snapshot.available),
            ),
        )

    def find_record_by_video_path(
        self, video_path: str, *, post_url: Optional[str] = None
    ) -> Optional[VideoRecord]:
        row = self._conn.execute(
            "SELECT * FROM video_records WHERE video_path = ?"
            " AND (? IS NULL OR post_url = ?) ORDER BY id DESC",
            (video_path, post_url, post_url),
        ).fetchone()
        return self._record(row) if row else None

    def reddit_snapshots(self, record_id: int) -> list[RedditSnapshot]:
        rows = self._conn.execute(
            "SELECT * FROM reddit_snapshots WHERE record_id = ? ORDER BY id",
            (record_id,),
        ).fetchall()
        return [
            RedditSnapshot(
                taken_at=_from_iso(row["taken_at"]),
                source=row["source"],
                score=row["score"],
                num_comments=row["num_comments"],
                upvote_ratio=row["upvote_ratio"],
                available=bool(row["available"]),
            )
            for row in rows
        ]

    @staticmethod
    def _record(row: sqlite3.Row) -> VideoRecord:
        grade = None
        if row["grade_overall"] is not None:
            grade = ModelGrade(
                overall=row["grade_overall"],
                verdict=row["grade_verdict"],
                **{f: row[f"grade_{f}"] for f in _GRADE_FIELDS},
            )
        recipe = None
        if row["story_prompt_version"] is not None:
            recipe = ProductionRecipe(**{f: row[f] for f in _RECIPE_FIELDS})
        return VideoRecord(
            id=row["id"],
            created_at=_from_iso(row["created_at"]),
            run_id=row["run_id"],
            video_path=row["video_path"],
            title=row["title"],
            summary=row["summary"],
            post_url=row["post_url"],
            community=row["community"] or "",
            author=row["author"] or "",
            post_created_utc=_from_iso(row["post_created_utc"]),
            part_index=row["part_index"],
            part_count=row["part_count"],
            language=row["language"] or "",
            duration_seconds=row["duration_seconds"],
            grade=grade,
            deterministic_score=row["deterministic_score"],
            recipe=recipe,
            hashtags=_tags_list(row["hashtags"]),
            tiktok_video_id=row["tiktok_video_id"],
            imported=bool(row["imported"]),
        )

    def add_publish_attempt(self, record_id: int, attempt: PublishAttempt) -> None:
        tags = _tags_text(attempt.hashtags)
        with self._tx() as db:
            db.execute(
                "INSERT INTO publish_attempts (record_id, attempted_at, status,"
                " scheduled_at, hashtags, publish_result, error)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    record_id,
                    _to_iso(attempt.attempted_at),
                    attempt.status,
                    _to_iso(attempt.scheduled_at),
                    tags,
                    attempt.publish_result,
                    attempt.error,
                ),
            )
            # The record keeps the hashtags of its first attempt that had any.
            db.execute(
                "UPDATE video_records SET hashtags = ? WHERE id = ? AND hashtags = ''",
                (tags, record_id),
            )

    def publish_attempts(self, record_id: int) -> list[PublishAttempt]:
        rows = self._conn.execute(
            "SELECT * FROM publish_attempts WHERE record_id = ? ORDER BY id",
            (record_id,),
        ).fetchall()
        return [
            PublishAttempt(
                attempted_at=_from_iso(row["attempted_at"]),
                status=row["status"],
                scheduled_at=_from_iso(row["scheduled_at"]),
                hashtags=_tags_list(row["hashtags"]),
                publish_result=row["publish_result"],
                error=row["error"],
            )
            for row in rows
        ]
