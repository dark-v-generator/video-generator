"""The history contract, held by the SQLite store and the in-memory fake alike."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from src.entities.history import (
    ModelGrade,
    ProductionRecipe,
    PublishAttempt,
    RedditSnapshot,
    RunSummary,
    VideoRecord,
)
from src.storage import HistoryConflictError, SqliteHistoryStore
from tests.fakes.memory_history import InMemoryHistoryStore

T0 = datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc)
SKIPPED = {
    "content_filter": 1,
    "script": 0,
    "render": 0,
    "publish": 0,
    "not_needed": 2,
}


@pytest.fixture(params=["sqlite", "memory"])
def store(request, tmp_path):
    if request.param == "sqlite":
        return SqliteHistoryStore(str(tmp_path / "nested" / "history.sqlite"))
    return InMemoryHistoryStore()


def record(video_path="out/story_01.mp4", **overrides) -> VideoRecord:
    fields = dict(
        created_at=T0,
        run_id=1,
        video_path=video_path,
        title="A vizinha e o bolo",
        summary="Resumo",
        post_url="https://reddit.com/r/contos/comments/p1/",
        community="r/contos",
        author="autor1",
        post_created_utc=T0 - timedelta(days=1),
        language="pt-br",
        grade=ModelGrade(
            overall=82.0,
            verdict="Excelente",
            retention=80.0,
            quality=85.0,
            virality=78.0,
            tiktok_fit=90.0,
            hook=77.0,
        ),
        deterministic_score=0.7,
        recipe=ProductionRecipe.empty(),
    )
    return VideoRecord(**{**fields, **overrides})


def discovery(score=100) -> RedditSnapshot:
    return RedditSnapshot(
        taken_at=T0, source="discovery", score=score, num_comments=10, upvote_ratio=0.9
    )


def attempt(status="scheduled", minutes=0, **overrides) -> PublishAttempt:
    fields = dict(
        attempted_at=T0 + timedelta(minutes=minutes),
        status=status,
        scheduled_at=T0 + timedelta(hours=2) if status == "scheduled" else None,
        hashtags=["fyp", "reddit"],
        publish_result="https://tiktok/1" if status == "scheduled" else "",
        error="" if status == "scheduled" else "boom",
    )
    return PublishAttempt(**{**fields, **overrides})


def test_the_sqlite_schema_is_created_from_nothing(tmp_path):
    path = tmp_path / "a" / "b" / "history.sqlite"

    SqliteHistoryStore(str(path))

    tables = {
        row[0]
        for row in sqlite3.connect(path).execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert tables == {
        "run_summaries",
        "video_records",
        "reddit_snapshots",
        "publish_attempts",
        "collections",
        "performance_snapshots",
    }


def test_a_run_opens_with_zero_counts_and_finish_completes_it(store):
    run_id = store.start_run(mode="generate", requested=3, started_at=T0)

    opened = store.run_summary(run_id)
    assert (opened.mode, opened.requested, opened.finished_at) == ("generate", 3, None)
    assert opened.produced == 0

    store.finish_run(
        run_id,
        RunSummary(
            started_at=T0,
            finished_at=T0 + timedelta(minutes=5),
            mode="generate",
            requested=3,
            target=3,
            candidates_found=5,
            produced=2,
            scheduled=0,
            skipped=SKIPPED,
            stopped_reason="",
        ),
    )

    finished = store.run_summary(run_id)
    assert finished.id == run_id
    assert finished.finished_at == T0 + timedelta(minutes=5)
    assert (finished.target, finished.candidates_found, finished.produced) == (3, 5, 2)
    assert finished.skipped == SKIPPED


def test_finishing_a_run_that_was_never_started_raises(store):
    summary = RunSummary(T0, T0, "run", 1, 1, 1, 1, 1, {})
    with pytest.raises(HistoryConflictError):
        store.finish_run(99, summary)


def test_a_record_keeps_its_discovery_signals(store):
    record_id = store.add_video_record(record(), discovery())

    saved = store.find_record_by_video_path("out/story_01.mp4")
    assert saved == record(id=record_id)
    assert saved.imported is False
    assert store.reddit_snapshots(record_id) == [discovery()]
    assert store.publish_attempts(record_id) == []


def test_a_failed_then_a_scheduled_attempt_are_both_kept(store):
    record_id = store.add_video_record(record(), discovery())

    store.add_publish_attempt(record_id, attempt("failed", minutes=0, hashtags=[]))
    store.add_publish_attempt(record_id, attempt("scheduled", minutes=60))

    assert store.publish_attempts(record_id) == [
        attempt("failed", minutes=0, hashtags=[]),
        attempt("scheduled", minutes=60),
    ]
    # The record takes the hashtags of the first attempt that had any.
    assert store.find_record_by_video_path("out/story_01.mp4").hashtags == [
        "fyp",
        "reddit",
    ]


def test_the_same_attempt_twice_raises(store):
    record_id = store.add_video_record(record(), discovery())
    store.add_publish_attempt(record_id, attempt())

    with pytest.raises(HistoryConflictError):
        store.add_publish_attempt(record_id, attempt())


def test_an_attempt_for_a_missing_record_raises(store):
    with pytest.raises(HistoryConflictError):
        store.add_publish_attempt(42, attempt())


def test_the_same_video_path_twice_raises(store):
    store.add_video_record(record(), discovery())

    with pytest.raises(HistoryConflictError):
        store.add_video_record(record(), discovery())


def test_an_unknown_video_path_finds_nothing(store):
    store.add_video_record(record(), discovery())

    assert store.find_record_by_video_path("out/story_02.mp4") is None


def test_a_record_without_discovery_is_imported(store):
    minimal = VideoRecord(
        created_at=T0,
        run_id=None,
        video_path="old/story_01.mp4",
        title="Antiga",
        summary="",
        post_url="https://reddit.com/x",
    )

    record_id = store.add_video_record(minimal, None)

    saved = store.find_record_by_video_path("old/story_01.mp4")
    assert saved.imported is True
    assert saved.grade is None and saved.recipe is None
    assert store.reddit_snapshots(record_id) == []


def test_dates_come_back_in_utc(store):
    local = datetime(2026, 9, 25, 7, 0, tzinfo=timezone(timedelta(hours=-3)))
    run_id = store.start_run(mode="run", requested=1, started_at=local)
    record_id = store.add_video_record(record(created_at=local), discovery())
    store.add_publish_attempt(record_id, attempt(attempted_at=local))

    started = store.run_summary(run_id).started_at
    created = store.find_record_by_video_path("out/story_01.mp4").created_at
    (attempted,) = store.publish_attempts(record_id)
    for value in (started, created, attempted.attempted_at):
        assert value.tzinfo == timezone.utc
        assert value == T0
