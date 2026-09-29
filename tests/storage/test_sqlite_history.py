"""The history contract, held by the SQLite store and the in-memory fake alike."""

import dataclasses
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from src.entities.history import (
    CROSSED_COLUMNS,
    Collection,
    GoalCounts,
    ModelGrade,
    PerformanceMetrics,
    PerformanceSnapshot,
    ProductionRecipe,
    PublishAttempt,
    RedditSnapshot,
    RunSummary,
    VideoRecord,
)
from src.storage import HistoryConflictError, SqliteHistoryStore, UnknownColumnError
from src.storage.sqlite_history import (
    _AUDIENCE_COLUMNS_SQL,
    _EXPLORATION_COLUMNS_SQL,
    _RECIPE_ADDED_COLUMNS_SQL,
    SCHEMA,
)
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


def test_a_path_reused_by_the_next_run_finds_the_newest_record(store):
    """Every daily run writes output/daily/story_01.mp4 again."""
    first = store.add_video_record(record(title="Yesterday"), discovery())
    store.add_publish_attempt(first, attempt())

    second = store.add_video_record(record(title="Today"), discovery())

    assert second != first
    assert store.find_record_by_video_path("out/story_01.mp4").title == "Today"
    assert len(store.publish_attempts(first)) == 1
    assert store.publish_attempts(second) == []


def test_a_reused_path_finds_the_record_made_from_a_given_post(store):
    first = store.add_video_record(record(post_url="yesterday"), discovery())
    store.add_video_record(record(post_url="today"), discovery())

    found = store.find_record_by_video_path("out/story_01.mp4", post_url="yesterday")

    assert found.id == first
    assert store.find_record_by_video_path("out/story_01.mp4", post_url="never") is None


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


def test_a_history_from_when_paths_were_unique_is_rebuilt_keeping_its_rows(tmp_path):
    path = str(tmp_path / "history.sqlite")
    old = sqlite3.connect(path)
    old.executescript(
        SCHEMA.replace("video_path TEXT NOT NULL,", "video_path TEXT NOT NULL UNIQUE,")
    )
    old.execute(
        "INSERT INTO video_records (created_at, video_path, title, post_url)"
        " VALUES ('2026-09-29T10:00:00+00:00', 'out/story_01.mp4', 'Yesterday', 'u')"
    )
    old.execute(
        "INSERT INTO publish_attempts (record_id, attempted_at, status)"
        " VALUES (1, '2026-09-29T10:05:00+00:00', 'scheduled')"
    )
    old.commit()
    old.close()

    store = SqliteHistoryStore(path)
    today = store.add_video_record(record(title="Today"), discovery())

    assert today == 2
    assert store.find_record_by_video_path("out/story_01.mp4").title == "Today"
    assert [a.status for a in store.publish_attempts(1)] == ["scheduled"]
    # Still enforced after the rebuild.
    with pytest.raises(HistoryConflictError):
        store.add_publish_attempt(42, attempt())
    check = sqlite3.connect(path)
    assert check.execute("PRAGMA foreign_key_check").fetchall() == []


# --------------------------------------------------------------------------
# Collections (M4)
# --------------------------------------------------------------------------

COLLECTED = T0 + timedelta(days=3)


def collection(matched=1) -> Collection:
    return Collection(
        started_at=COLLECTED,
        finished_at=COLLECTED + timedelta(minutes=5),
        lookback_days=30,
        matched=matched,
        unmatched=2,
        ambiguous=0,
        reddit_refreshed=matched,
    )


def performance(video_id="v1", views=1000, **metrics) -> PerformanceSnapshot:
    return PerformanceSnapshot(
        taken_at=COLLECTED,
        tiktok_video_id=video_id,
        metrics=PerformanceMetrics(views=views, likes=50, **metrics),
        tiktok_created_at=T0 + timedelta(hours=2),
    )


def refreshed(score=150) -> RedditSnapshot:
    return RedditSnapshot(
        taken_at=COLLECTED,
        source="collection",
        score=score,
        num_comments=12,
        upvote_ratio=0.91,
    )


def scheduled_record(store, path, *, slot_hours=2, status="scheduled") -> int:
    record_id = store.add_video_record(record(path), discovery())
    store.add_publish_attempt(
        record_id,
        attempt(status, scheduled_at=T0 + timedelta(hours=slot_hours)),
    )
    return record_id


def test_published_records_are_those_with_a_slot_since_and_their_newest_slot(store):
    recent = scheduled_record(store, "out/a.mp4", slot_hours=2)
    store.add_publish_attempt(
        recent,
        attempt(minutes=90, scheduled_at=T0 + timedelta(hours=26)),
    )
    scheduled_record(store, "out/old.mp4", slot_hours=-72)
    store.add_video_record(record("out/never.mp4"), discovery())
    no_slot = store.add_video_record(record("out/no_slot.mp4"), discovery())
    store.add_publish_attempt(no_slot, attempt("failed", scheduled_at=None))

    published = store.published_records(T0)

    assert [(p.record.id, p.scheduled_at) for p in published] == [
        (recent, T0 + timedelta(hours=26))
    ]


def test_a_failed_attempt_for_a_slot_is_published_since_tiktok_may_have_taken_it(
    store,
):
    """Seen on the server: the publisher logged failures for videos TikTok
    scheduled at exactly that slot."""
    failed = scheduled_record(store, "out/failed.mp4", slot_hours=5, status="failed")
    retried = scheduled_record(store, "out/retried.mp4", slot_hours=5, status="failed")
    store.add_publish_attempt(
        retried, attempt(minutes=60, scheduled_at=T0 + timedelta(hours=3))
    )
    store.add_publish_attempt(
        retried,
        attempt("failed", minutes=120, scheduled_at=T0 + timedelta(hours=9)),
    )

    published = store.published_records(T0)

    # The slot of a scheduled attempt wins over a later failed one.
    assert [(p.record.id, p.scheduled_at) for p in published] == [
        (failed, T0 + timedelta(hours=5)),
        (retried, T0 + timedelta(hours=3)),
    ]


def test_a_record_that_knows_its_video_is_published_whatever_its_slot(store):
    old = scheduled_record(store, "out/old.mp4", slot_hours=-72)
    store.assign_tiktok_video(old, "v-old")

    assert [p.record.id for p in store.published_records(T0)] == [old]


def test_a_collection_writes_its_row_snapshots_and_video_ids(store):
    record_id = scheduled_record(store, "out/a.mp4")

    collection_id = store.record_collection(
        collection(), {record_id: performance()}, {record_id: refreshed()}
    )

    assert collection_id == 1
    assert store.collections() == [collection()]
    assert store.performance_snapshots(record_id) == [performance()]
    assert store.reddit_snapshots(record_id) == [discovery(), refreshed()]
    assert store.video_record(record_id).tiktok_video_id == "v1"


def test_a_metric_the_studio_did_not_show_comes_back_none(store):
    record_id = scheduled_record(store, "out/a.mp4")

    store.record_collection(
        collection(), {record_id: performance(saves=None, avg_watch_seconds=None)}, {}
    )

    metrics = store.performance_snapshots(record_id)[0].metrics
    assert metrics.saves is None and metrics.avg_watch_seconds is None
    assert metrics.views == 1000


AUDIENCE = dict(
    new_followers=6,
    retention=(1.0, 0.86, 0.76, 0.69),
    traffic_sources={"For You": 0.977, "Search": 0.023},
)


def test_a_collection_keeps_the_audience_signals(store):
    record_id = scheduled_record(store, "out/a.mp4")

    store.record_collection(collection(), {record_id: performance(**AUDIENCE)}, {})

    assert store.performance_snapshots(record_id) == [performance(**AUDIENCE)]


def test_a_history_from_before_the_audience_signals_gains_their_columns(tmp_path):
    path = str(tmp_path / "history.sqlite")
    old = sqlite3.connect(path)
    old.executescript(SCHEMA.replace(_AUDIENCE_COLUMNS_SQL, ""))
    old.executescript(
        "INSERT INTO video_records (created_at, video_path, title, post_url)"
        " VALUES ('2026-09-25T10:00:00+00:00', 'out/a.mp4', 'Before', 'u');"
        "INSERT INTO collections (started_at, finished_at)"
        " VALUES ('2026-09-28T10:00:00+00:00', '2026-09-28T10:05:00+00:00');"
        "INSERT INTO performance_snapshots (record_id, collection_id, taken_at,"
        " tiktok_video_id, views) VALUES (1, 1, '2026-09-28T10:00:00+00:00', 'v1', 9);"
    )
    old.close()

    store = SqliteHistoryStore(path)
    store.record_collection(collection(), {1: performance(**AUDIENCE)}, {})

    before, after = store.performance_snapshots(1)
    assert before.metrics == PerformanceMetrics(views=9)
    assert after == performance(**AUDIENCE)
    # Opening it again finds the columns already there.
    assert len(SqliteHistoryStore(path).performance_snapshots(1)) == 2


def test_the_recipe_keeps_the_hashtags_prompt_version(store):
    recipe = dataclasses.replace(ProductionRecipe.empty(), hashtags_prompt_version="h1")
    store.add_video_record(record(recipe=recipe), discovery())

    saved = store.find_record_by_video_path("out/story_01.mp4")

    assert saved.recipe.hashtags_prompt_version == "h1"
    assert ids(store.crossed_view(filters={"hashtags_prompt_version": "h1"})) == [
        saved.id
    ]


def test_a_history_from_before_the_hashtags_version_gains_its_column(tmp_path):
    path = str(tmp_path / "history.sqlite")
    old = sqlite3.connect(path)
    old.executescript(SCHEMA.replace(_RECIPE_ADDED_COLUMNS_SQL, ""))
    old.executescript(
        "INSERT INTO video_records (created_at, video_path, title, post_url,"
        " story_prompt_version) VALUES ('2026-09-25T10:00:00+00:00', 'out/a.mp4',"
        " 'Before', 'u', 's1');"
    )
    old.close()

    store = SqliteHistoryStore(path)

    before = store.find_record_by_video_path("out/a.mp4")
    assert before.recipe.story_prompt_version == "s1"
    assert before.recipe.hashtags_prompt_version is None
    store.add_video_record(record("out/b.mp4"), discovery())
    assert len(SqliteHistoryStore(path).crossed_view()) == 2


def test_a_second_collection_adds_snapshots_and_keeps_the_first(store):
    record_id = scheduled_record(store, "out/a.mp4")
    store.record_collection(collection(), {record_id: performance(views=10)}, {})

    store.record_collection(collection(), {record_id: performance(views=99)}, {})

    assert [s.metrics.views for s in store.performance_snapshots(record_id)] == [
        10,
        99,
    ]
    assert len(store.collections()) == 2


def test_a_collection_that_fails_midway_leaves_nothing(store):
    first = scheduled_record(store, "out/a.mp4")
    last = scheduled_record(store, "out/b.mp4")

    with pytest.raises(HistoryConflictError):
        store.record_collection(
            collection(matched=3),
            {first: performance("v1"), 404: performance("v2"), last: performance("v3")},
            {first: refreshed()},
        )

    assert store.collections() == []
    assert store.performance_snapshots(first) == []
    assert store.reddit_snapshots(first) == [discovery()]
    assert store.video_record(first).tiktok_video_id is None


def test_one_tiktok_video_on_two_records_raises(store):
    first = scheduled_record(store, "out/a.mp4")
    second = scheduled_record(store, "out/b.mp4")
    store.assign_tiktok_video(first, "v1")

    with pytest.raises(HistoryConflictError):
        store.record_collection(collection(), {second: performance("v1")}, {})
    with pytest.raises(HistoryConflictError):
        store.assign_tiktok_video(second, "v1")

    assert store.collections() == []
    assert store.video_record(second).tiktok_video_id is None


def test_assigning_a_video_to_a_missing_record_raises(store):
    with pytest.raises(HistoryConflictError):
        store.assign_tiktok_video(42, "v1")


def graded(overall: float, verdict: str, prompt: str = "v1") -> dict:
    return dict(
        grade=ModelGrade(overall=overall, verdict=verdict),
        recipe=dataclasses.replace(
            ProductionRecipe.empty(), story_prompt_version=prompt, writer_model="m"
        ),
    )


@pytest.fixture
def crossed(store):
    """Four videos: two collected (twice for the first), one published but not
    collected yet, and one imported from before the history."""
    loved = store.add_video_record(
        record("out/loved.mp4", **graded(90, "Excelente")), discovery(score=100)
    )
    flopped = store.add_video_record(
        record("out/flopped.mp4", **graded(60, "Mediana", prompt="v2")),
        discovery(score=40),
    )
    waiting = store.add_video_record(
        record("out/waiting.mp4", **graded(85, "Excelente")), discovery(score=70)
    )
    imported = store.add_video_record(
        record(
            "out/imported.mp4",
            created_at=T0 - timedelta(days=30),
            grade=None,
            recipe=None,
        ),
        None,
    )
    for minutes, record_id in enumerate([loved, flopped, waiting, imported]):
        store.add_publish_attempt(record_id, attempt("failed", minutes=minutes))
    store.add_publish_attempt(loved, attempt(minutes=10))
    store.record_collection(
        collection(matched=2),
        {loved: performance("v1", views=300), flopped: performance("v2", views=9000)},
        {loved: refreshed(score=120), flopped: refreshed(score=45)},
    )
    store.record_collection(
        collection(matched=1),
        {loved: performance("v1", views=500)},
        {loved: refreshed(score=150)},
    )
    return dict(loved=loved, flopped=flopped, waiting=waiting, imported=imported)


def ids(rows) -> list[int]:
    return [row.record.id for row in rows]


def test_the_crossed_view_has_every_video_with_its_newest_numbers(store, crossed):
    rows = {row.record.id: row for row in store.crossed_view()}

    assert list(rows) == list(crossed.values())
    loved = rows[crossed["loved"]]
    assert loved.discovery == discovery(score=100)
    assert loved.latest_reddit == refreshed(score=150)
    assert loved.latest_performance == performance("v1", views=500)
    assert loved.last_attempt == attempt(minutes=10)
    assert loved.record.tiktok_video_id == "v1"
    assert loved.columns()["latest_views"] == 500
    assert loved.columns()["discovery_score"] == 100
    assert loved.columns()["latest_reddit_score"] == 150
    assert loved.columns()["last_attempt_status"] == "scheduled"


def test_a_video_without_a_collection_is_there_with_empty_numbers(store, crossed):
    rows = {row.record.id: row for row in store.crossed_view()}

    waiting = rows[crossed["waiting"]].columns()
    assert waiting["grade_overall"] == 85 and waiting["discovery_score"] == 70
    assert waiting["latest_views"] is None and waiting["latest_reddit_score"] is None
    assert waiting["last_attempt_status"] == "failed"
    imported = rows[crossed["imported"]].columns()
    assert imported["imported"] is True
    assert imported["discovery_score"] is None and imported["grade_overall"] is None
    assert imported["story_prompt_version"] is None


def test_sorting_by_grade_puts_the_ungraded_last(store, crossed):
    rows = store.crossed_view(sort=("grade_overall", True))

    assert ids(rows) == [
        crossed[k] for k in ("loved", "waiting", "flopped", "imported")
    ]


def test_sorting_by_views_puts_the_uncollected_last_in_either_order(store, crossed):
    uncollected = [crossed["waiting"], crossed["imported"]]

    assert ids(store.crossed_view(sort=("latest_views", False))) == [
        crossed["loved"],
        crossed["flopped"],
        *uncollected,
    ]
    assert ids(store.crossed_view(sort=("latest_views", True))) == [
        crossed["flopped"],
        crossed["loved"],
        *uncollected,
    ]


def test_ties_keep_the_record_order(store, crossed):
    rows = store.crossed_view(sort=("grade_verdict", True))

    assert ids(rows) == [
        crossed[k] for k in ("flopped", "loved", "waiting", "imported")
    ]


def test_filters_keep_the_rows_whose_column_equals_the_text(store, crossed):
    assert ids(store.crossed_view(filters={"story_prompt_version": "v2"})) == [
        crossed["flopped"]
    ]
    assert ids(
        store.crossed_view(filters={"grade_verdict": "Excelente", "writer_model": "m"})
    ) == [crossed["loved"], crossed["waiting"]]
    # Numbers match as numbers, booleans as 1 and 0.
    assert ids(store.crossed_view(filters={"grade_overall": "90"})) == [
        crossed["loved"]
    ]
    assert ids(store.crossed_view(filters={"imported": "1"})) == [crossed["imported"]]
    assert ids(store.crossed_view(filters={"tiktok_video_id": "v2"})) == [
        crossed["flopped"]
    ]
    assert store.crossed_view(filters={"latest_views": "abc"}) == []


def test_since_leaves_out_older_records(store, crossed):
    assert crossed["imported"] not in ids(store.crossed_view(since=T0))
    assert len(store.crossed_view(since=T0 - timedelta(days=31))) == 4


@pytest.mark.parametrize(
    "call",
    [
        dict(sort=("views", True)),
        dict(filters={"grade": "90"}),
        dict(filters={"title; DROP TABLE video_records": "x"}),
    ],
)
def test_an_unknown_column_raises_naming_the_valid_ones(store, crossed, call):
    with pytest.raises(UnknownColumnError) as error:
        store.crossed_view(**call)

    assert "latest_views" in str(error.value) and "grade_overall" in str(error.value)
    assert len(store.crossed_view()) == 4


def test_a_crossed_row_flattens_into_the_crossed_columns(store, crossed):
    for row in store.crossed_view():
        assert tuple(row.columns()) == CROSSED_COLUMNS


def test_the_crossed_view_shows_the_hook_and_the_for_you_share(store, crossed):
    store.record_collection(
        collection(matched=2),
        {
            crossed["loved"]: performance("v1", views=600, **AUDIENCE),
            crossed["flopped"]: performance(
                "v2",
                views=9100,
                retention=(1.0, 0.5, 0.4, 0.3),
                traffic_sources={"Search": 1.0},
            ),
        },
        {},
    )

    rows = store.crossed_view(sort=("latest_retained_3s", True))

    assert ids(rows)[:2] == [crossed["loved"], crossed["flopped"]]
    loved, flopped = rows[0].columns(), rows[1].columns()
    assert loved["latest_retained_3s"] == 0.69
    # Past the end of the curve, as a short video would be at 10 s.
    assert loved["latest_retained_10s"] is None
    assert loved["latest_new_followers"] == 6
    assert loved["latest_for_you_ratio"] == 0.977
    # A breakdown without For You means none of the views came from it.
    assert flopped["latest_for_you_ratio"] == 0.0
    assert rows[2].columns()["latest_for_you_ratio"] is None
    assert ids(store.crossed_view(filters={"latest_for_you_ratio": "0"})) == [
        crossed["flopped"]
    ]


# --------------------------------------------------------------------------
# What each video was made for (feature 006, M4)
# --------------------------------------------------------------------------


def explored(path: str, goal="base", experiment="E001", fit=81.5, cycle=2, **kw):
    return record(
        path,
        goal=goal,
        exploration_experiment=experiment,
        exploration_fit=fit,
        cycle=cycle,
        **kw,
    )


def test_a_record_keeps_its_goal_exploration_grade_and_cycle(store):
    recipe = dataclasses.replace(
        ProductionRecipe.empty(), exploration_prompt_version="x1"
    )
    record_id = store.add_video_record(
        explored("out/a.mp4", recipe=recipe), discovery()
    )

    saved = store.video_record(record_id)

    assert (saved.goal, saved.exploration_experiment) == ("base", "E001")
    assert (saved.exploration_fit, saved.cycle) == (81.5, 2)
    assert saved.recipe.exploration_prompt_version == "x1"


def test_a_record_made_without_a_plan_keeps_them_empty(store):
    record_id = store.add_video_record(record(), discovery())

    saved = store.video_record(record_id)

    assert (saved.goal, saved.exploration_experiment) == (None, None)
    assert (saved.exploration_fit, saved.cycle) == (None, None)


def test_the_crossed_view_sorts_and_filters_by_goal_fit_and_cycle(store):
    low = store.add_video_record(explored("out/a.mp4", fit=40.0), discovery())
    high = store.add_video_record(explored("out/b.mp4", goal="E001"), discovery())
    plain = store.add_video_record(record("out/c.mp4"), discovery())

    assert ids(store.crossed_view(sort=("exploration_fit", True))) == [
        high,
        low,
        plain,
    ]
    assert ids(store.crossed_view(filters={"goal": "E001"})) == [high]
    assert ids(store.crossed_view(filters={"cycle": "2"})) == [low, high]
    columns = store.crossed_view(filters={"goal": "E001"})[0].columns()
    assert (columns["exploration_experiment"], columns["cycle"]) == ("E001", 2)


def test_goal_counts_are_the_videos_made_since_and_those_for_an_experiment(store):
    day = T0.date()
    store.add_video_record(
        explored("out/old.mp4", created_at=T0 - timedelta(days=1)), discovery()
    )
    store.add_video_record(explored("out/a.mp4"), discovery())
    store.add_video_record(explored("out/b.mp4", goal="E001"), discovery())
    store.add_video_record(explored("out/c.mp4", goal="E002"), discovery())
    # From before the history kept goals: made, but not for an experiment.
    store.add_video_record(record("out/d.mp4"), discovery())
    # Imported videos were not made by a run.
    store.add_video_record(explored("out/e.mp4", goal="E001"), None)

    counts = store.goal_counts(day)

    assert (counts.total, counts.exploration) == (4, 2)
    assert store.goal_counts(day + timedelta(days=1)) == GoalCounts(0, 0)


def test_a_history_from_before_the_goals_gains_their_columns(tmp_path):
    path = str(tmp_path / "history.sqlite")
    old = sqlite3.connect(path)
    before = SCHEMA.replace(_EXPLORATION_COLUMNS_SQL, "").replace(
        ", exploration_prompt_version TEXT", ""
    )
    assert "goal" not in before and "exploration_prompt_version" not in before
    old.executescript(before)
    for n in range(3):
        old.execute(
            "INSERT INTO video_records (created_at, video_path, title, post_url,"
            " story_prompt_version, hashtags_prompt_version)"
            f" VALUES ('2026-09-25T10:00:00+00:00', 'out/{n}.mp4', 'Before', 'u',"
            " 's1', 'h1')"
        )
    old.commit()
    old.close()

    store = SqliteHistoryStore(path)

    rows = store.crossed_view()
    assert len(rows) == 3
    assert {
        (r.record.goal, r.record.cycle, r.record.exploration_fit) for r in rows
    } == {(None, None, None)}
    assert rows[0].record.recipe.hashtags_prompt_version == "h1"
    assert rows[0].record.recipe.exploration_prompt_version is None
    store.add_video_record(explored("out/new.mp4"), discovery())
    # Opening it again finds the columns already there.
    assert len(SqliteHistoryStore(path).crossed_view(filters={"goal": "base"})) == 1
