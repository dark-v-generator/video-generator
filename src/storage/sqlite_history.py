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
    CROSSED_COLUMNS,
    FOR_YOU,
    RETAINED_AT_SECONDS,
    Collection,
    CrossedRow,
    ModelGrade,
    PerformanceMetrics,
    PerformanceSnapshot,
    ProductionRecipe,
    PublishAttempt,
    PublishedRecord,
    RedditSnapshot,
    RunMode,
    RunSummary,
    VideoRecord,
)
from .history_contract import (
    HistoryConflictError,
    HistoryError,
    check_crossed_columns,
)

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

# Added after the first collections: a history from before gets them, NULL in
# its old rows. retention and traffic_sources are JSON (a list, an object).
_AUDIENCE_COLUMNS = {
    "new_followers": "INTEGER",
    "retention": "TEXT",
    "traffic_sources": "TEXT",
}
_AUDIENCE_COLUMNS_SQL = "".join(
    f", {name} {kind}" for name, kind in _AUDIENCE_COLUMNS.items()
)

# Recipe parts versioned after the first records: NULL in the rows before.
_RECIPE_ADDED_COLUMNS = {"hashtags_prompt_version": "TEXT"}
_RECIPE_ADDED_COLUMNS_SQL = "".join(
    f", {name} {kind}" for name, kind in _RECIPE_ADDED_COLUMNS.items()
)
_ADDED_COLUMNS = {
    "performance_snapshots": _AUDIENCE_COLUMNS,
    "video_records": _RECIPE_ADDED_COLUMNS,
}

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS run_summaries (
  id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
  mode TEXT NOT NULL, requested INTEGER, target INTEGER, candidates_found INTEGER,
  produced INTEGER, scheduled INTEGER, skipped_json TEXT NOT NULL,
  stopped_reason TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS video_records (
  {_VIDEO_RECORDS_COLUMNS}{_RECIPE_ADDED_COLUMNS_SQL});
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
  tiktok_created_at TEXT{_AUDIENCE_COLUMNS_SQL});
CREATE INDEX IF NOT EXISTS reddit_snapshots_by_record ON reddit_snapshots (record_id);
CREATE INDEX IF NOT EXISTS publish_attempts_by_record ON publish_attempts (record_id);
CREATE INDEX IF NOT EXISTS performance_snapshots_by_record
  ON performance_snapshots (record_id);
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
    *_RECIPE_ADDED_COLUMNS,
]
_METRIC_FIELDS = [
    "views",
    "likes",
    "comments",
    "shares",
    "saves",
    "avg_watch_seconds",
    "full_watch_ratio",
    "new_followers",
]
_JSON_METRIC_FIELDS = ["retention", "traffic_sources"]
_COLLECTION_FIELDS = [
    "lookback_days",
    "matched",
    "unmatched",
    "ambiguous",
    "reddit_refreshed",
]


_REDDIT_FIELDS = [
    "taken_at",
    "source",
    "score",
    "num_comments",
    "upvote_ratio",
    "available",
]
_ATTEMPT_FIELDS = [
    "attempted_at",
    "status",
    "scheduled_at",
    "hashtags",
    "publish_result",
    "error",
]
_PERFORMANCE_FIELDS = [
    "taken_at",
    "tiktok_video_id",
    *_METRIC_FIELDS,
    *_JSON_METRIC_FIELDS,
    "tiktok_created_at",
]

# The crossed view joins each record to the newest of its snapshots and
# attempts, under these aliases and column prefixes.
_CROSSED_JOINS = {
    "d": ("reddit_snapshots", _REDDIT_FIELDS, " AND source = 'discovery'"),
    "c": ("reddit_snapshots", _REDDIT_FIELDS, " AND source = 'collection'"),
    "p": ("performance_snapshots", _PERFORMANCE_FIELDS, ""),
    "a": ("publish_attempts", _ATTEMPT_FIELDS, ""),
}
_CROSSED_FROM = "FROM video_records r" + "".join(
    f" LEFT JOIN {table} {alias} ON {alias}.id = (SELECT max(id) FROM {table}"
    f" WHERE record_id = r.id{condition})"
    for alias, (table, _, condition) in _CROSSED_JOINS.items()
)
_CROSSED_SELECT = "SELECT r.*, " + ", ".join(
    f"{alias}.{f} AS {alias}_{f}"
    for alias, (_, columns, _) in _CROSSED_JOINS.items()
    for f in columns
)
_REDDIT_NUMBERS = ["score", "num_comments", "upvote_ratio", "taken_at"]
# Each crossed column as SQL; the rest are video_records' own columns. Only
# these fixed strings reach the query, never a name the user typed.
_CROSSED_SQL = {
    **{name: f"r.{name}" for name in CROSSED_COLUMNS},
    "last_attempt_status": "a.status",
    "last_scheduled_at": "a.scheduled_at",
    **{f"discovery_{f}": f"d.{f}" for f in _REDDIT_NUMBERS},
    **{f"latest_reddit_{f}": f"c.{f}" for f in _REDDIT_NUMBERS},
    "latest_reddit_available": "c.available",
    **{f"latest_{f}": f"p.{f}" for f in _METRIC_FIELDS},
    **{
        f"latest_retained_{second}s": f"json_extract(p.retention, '$[{second}]')"
        for second in RETAINED_AT_SECONDS
    },
    "latest_for_you_ratio": (
        "CASE WHEN p.traffic_sources IS NULL THEN NULL ELSE"
        f" coalesce(json_extract(p.traffic_sources, '$.\"{FOR_YOU}\"'), 0.0) END"
    ),
    "latest_taken_at": "p.taken_at",
}


def _to_iso(value: Optional[datetime]) -> Optional[str]:
    return value.astimezone(timezone.utc).isoformat() if value else None


def _from_iso(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def _tags_text(tags: list[str]) -> str:
    return " ".join(f"#{tag}" for tag in tags)


def _tags_list(text: str) -> list[str]:
    return [tag.lstrip("#") for tag in text.split()]


def _number(text: str) -> Optional[float]:
    try:
        return float(text)
    except ValueError:
        return None


def _reddit_snapshot(row: sqlite3.Row, prefix: str = "") -> RedditSnapshot:
    return RedditSnapshot(
        taken_at=_from_iso(row[f"{prefix}taken_at"]),
        source=row[f"{prefix}source"],
        score=row[f"{prefix}score"],
        num_comments=row[f"{prefix}num_comments"],
        upvote_ratio=row[f"{prefix}upvote_ratio"],
        available=bool(row[f"{prefix}available"]),
    )


def _publish_attempt(row: sqlite3.Row, prefix: str = "") -> PublishAttempt:
    return PublishAttempt(
        attempted_at=_from_iso(row[f"{prefix}attempted_at"]),
        status=row[f"{prefix}status"],
        scheduled_at=_from_iso(row[f"{prefix}scheduled_at"]),
        hashtags=_tags_list(row[f"{prefix}hashtags"]),
        publish_result=row[f"{prefix}publish_result"],
        error=row[f"{prefix}error"],
    )


def _metric_values(metrics: PerformanceMetrics) -> list[object]:
    """The metrics in _METRIC_FIELDS then _JSON_METRIC_FIELDS order."""
    return [
        *(getattr(metrics, f) for f in _METRIC_FIELDS),
        *(
            None if getattr(metrics, f) is None else json.dumps(getattr(metrics, f))
            for f in _JSON_METRIC_FIELDS
        ),
    ]


def _performance_snapshot(row: sqlite3.Row, prefix: str = "") -> PerformanceSnapshot:
    retention = row[f"{prefix}retention"]
    traffic_sources = row[f"{prefix}traffic_sources"]
    return PerformanceSnapshot(
        taken_at=_from_iso(row[f"{prefix}taken_at"]),
        tiktok_video_id=row[f"{prefix}tiktok_video_id"],
        metrics=PerformanceMetrics(
            **{f: row[f"{prefix}{f}"] for f in _METRIC_FIELDS},
            retention=tuple(json.loads(retention)) if retention else None,
            traffic_sources=json.loads(traffic_sources) if traffic_sources else None,
        ),
        tiktok_created_at=_from_iso(row[f"{prefix}tiktok_created_at"]),
    )


class SqliteHistoryStore:
    def __init__(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        # Columns first: the rebuild copies rows whole into the full layout.
        self._add_columns()
        self._allow_reused_video_paths()

    def _add_columns(self) -> None:
        """A history from before a column was added gets it, empty in the
        rows it already has."""
        with self._tx() as db:
            for table, columns in _ADDED_COLUMNS.items():
                existing = {
                    column["name"]
                    for column in db.execute(f"PRAGMA table_info({table})")
                }
                for name, kind in columns.items():
                    if name not in existing:
                        db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")

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
            CREATE TABLE video_records_rebuilt (
              {_VIDEO_RECORDS_COLUMNS}{_RECIPE_ADDED_COLUMNS_SQL});
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
        return [_reddit_snapshot(row) for row in rows]

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
        return [_publish_attempt(row) for row in rows]

    def video_record(self, record_id: int) -> VideoRecord:
        row = self._conn.execute(
            "SELECT * FROM video_records WHERE id = ?", (record_id,)
        ).fetchone()
        if row is None:
            raise HistoryConflictError(f"No record {record_id}")
        return self._record(row)

    def published_records(self, since: datetime) -> list[PublishedRecord]:
        rows = self._conn.execute(
            "SELECT r.*, (SELECT a.scheduled_at FROM publish_attempts a"
            "  WHERE a.record_id = r.id AND a.scheduled_at IS NOT NULL"
            "  ORDER BY a.status = 'scheduled' DESC, a.id DESC LIMIT 1) AS last_slot"
            " FROM video_records r WHERE r.tiktok_video_id IS NOT NULL"
            " OR EXISTS (SELECT 1 FROM publish_attempts a WHERE a.record_id = r.id"
            "  AND a.scheduled_at >= ?)"
            " ORDER BY r.id",
            (_to_iso(since),),
        ).fetchall()
        return [
            PublishedRecord(
                record=self._record(row), scheduled_at=_from_iso(row["last_slot"])
            )
            for row in rows
        ]

    def record_collection(
        self,
        collection: Collection,
        performance: dict[int, PerformanceSnapshot],
        reddit: dict[int, RedditSnapshot],
    ) -> int:
        with self._tx() as db:
            collection_id = db.execute(
                "INSERT INTO collections (started_at, finished_at,"
                f" {', '.join(_COLLECTION_FIELDS)}) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    _to_iso(collection.started_at),
                    _to_iso(collection.finished_at),
                    *(getattr(collection, f) for f in _COLLECTION_FIELDS),
                ),
            ).lastrowid
            for record_id, snapshot in performance.items():
                values = (
                    record_id,
                    collection_id,
                    _to_iso(snapshot.taken_at),
                    snapshot.tiktok_video_id,
                    *_metric_values(snapshot.metrics),
                    _to_iso(snapshot.tiktok_created_at),
                )
                db.execute(
                    "INSERT INTO performance_snapshots (record_id, collection_id,"
                    " taken_at, tiktok_video_id,"
                    f" {', '.join([*_METRIC_FIELDS, *_JSON_METRIC_FIELDS])},"
                    f" tiktok_created_at) VALUES ({', '.join('?' * len(values))})",
                    values,
                )
                db.execute(
                    "UPDATE video_records SET tiktok_video_id = ? WHERE id = ?",
                    (snapshot.tiktok_video_id, record_id),
                )
            for record_id, snapshot in reddit.items():
                self._insert_reddit_snapshot(db, record_id, snapshot)
            return collection_id

    def assign_tiktok_video(self, record_id: int, tiktok_video_id: str) -> None:
        with self._tx() as db:
            cursor = db.execute(
                "UPDATE video_records SET tiktok_video_id = ? WHERE id = ?",
                (tiktok_video_id, record_id),
            )
            if cursor.rowcount != 1:
                raise HistoryConflictError(f"No record {record_id}")

    def performance_snapshots(self, record_id: int) -> list[PerformanceSnapshot]:
        rows = self._conn.execute(
            "SELECT * FROM performance_snapshots WHERE record_id = ? ORDER BY id",
            (record_id,),
        ).fetchall()
        return [_performance_snapshot(row) for row in rows]

    def collections(self) -> list[Collection]:
        rows = self._conn.execute("SELECT * FROM collections ORDER BY id").fetchall()
        return [
            Collection(
                started_at=_from_iso(row["started_at"]),
                finished_at=_from_iso(row["finished_at"]),
                **{f: row[f] for f in _COLLECTION_FIELDS},
            )
            for row in rows
        ]

    def crossed_view(
        self,
        *,
        since: Optional[datetime] = None,
        filters: Optional[dict[str, str]] = None,
        sort: Optional[tuple[str, bool]] = None,
    ) -> list[CrossedRow]:
        filters = filters or {}
        check_crossed_columns([*filters, *([sort[0]] if sort else [])])
        where, params = ["(? IS NULL OR r.created_at >= ?)"], [_to_iso(since)] * 2
        for name, wanted in filters.items():
            column = _CROSSED_SQL[name]
            # A number matches as a number (82 finds 82.0), anything else as text.
            where.append(
                f"CASE WHEN typeof({column}) IN ('integer', 'real')"
                f" THEN {column} = ? ELSE CAST({column} AS TEXT) = ? END"
            )
            params += [_number(wanted), wanted]
        order = "r.id"
        if sort:
            column, descending = _CROSSED_SQL[sort[0]], sort[1]
            order = (
                f"{column} IS NULL, {column} {'DESC' if descending else 'ASC'}, r.id"
            )
        rows = self._conn.execute(
            f"{_CROSSED_SELECT} {_CROSSED_FROM}"
            f" WHERE {' AND '.join(where)} ORDER BY {order}",
            params,
        ).fetchall()
        return [
            CrossedRow(
                record=self._record(row),
                discovery=_reddit_snapshot(row, "d_") if row["d_taken_at"] else None,
                latest_reddit=(
                    _reddit_snapshot(row, "c_") if row["c_taken_at"] else None
                ),
                latest_performance=(
                    _performance_snapshot(row, "p_") if row["p_taken_at"] else None
                ),
                last_attempt=(
                    _publish_attempt(row, "a_") if row["a_attempted_at"] else None
                ),
            )
            for row in rows
        ]
