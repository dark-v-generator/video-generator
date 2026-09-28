"""What a collection leaves in the history (US2), on both stores.

The history is seeded as the daily run leaves it: records with a discovery
snapshot and a scheduled attempt. The Studio is a fake source; Reddit goes
through the real discovery over the fake proxy, so removed posts are real
``RedditPostUnavailableError``s.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.capabilities.discovery import RedditStoryDiscovery
from src.entities.config import EvaluationConfig
from src.entities.configs.flows import CollectionConfig
from src.entities.history import (
    PerformanceMetrics,
    PerformanceSnapshot,
    PublishAttempt,
    RedditSnapshot,
    TikTokVideoStats,
    VideoRecord,
)
from src.entities.reddit_post import RedditPost
from src.flows.collect_performance import PerformanceCollection
from src.proxies.interfaces import TikTokSessionExpiredError, TikTokStudioLayoutError
from src.storage import SqliteHistoryStore
from tests.fakes.memory_history import InMemoryHistoryStore
from tests.fakes.performance import FakePerformanceSource
from tests.fakes.proxies import FakeRedditProxy

UTC = timezone.utc
NOW = datetime(2026, 9, 28, 15, 0, tzinfo=UTC)
LATER = NOW + timedelta(days=2)
SLOT = datetime(2026, 9, 25, 21, 0, tzinfo=UTC)
TAGS = "  #fyp  #storytime  #reddit"
FOUND = RedditSnapshot(
    taken_at=SLOT - timedelta(hours=10),
    source="discovery",
    score=100,
    num_comments=10,
    upvote_ratio=0.9,
)


@pytest.fixture(params=["memory", "sqlite"])
def history(request, tmp_path):
    if request.param == "memory":
        return InMemoryHistoryStore()
    return SqliteHistoryStore(str(tmp_path / "history.sqlite"))


def seed(history, title, *, post="p1", slot=SLOT) -> int:
    record_id = history.add_video_record(
        VideoRecord(
            created_at=slot - timedelta(hours=10),
            run_id=1,
            video_path=f"output/daily/{title}.mp4",
            title=title,
            summary="",
            post_url=f"https://www.reddit.com/r/t/comments/{post}/",
        ),
        FOUND,
    )
    history.add_publish_attempt(
        record_id,
        PublishAttempt(
            attempted_at=slot - timedelta(hours=9),
            status="scheduled",
            scheduled_at=slot,
            hashtags=["fyp", "storytime", "reddit"],
        ),
    )
    return record_id


def tiktok(video_id, title, *, posted=SLOT, views=500):
    return TikTokVideoStats(
        video_id=video_id,
        description=title + TAGS,
        created_at=posted + timedelta(minutes=2),
        metrics=PerformanceMetrics(
            views=views, likes=20, comments=3, shares=1, saves=2
        ),
    )


def analytics(views=500, **overrides) -> PerformanceMetrics:
    fields = dict(
        views=views,
        likes=20,
        comments=3,
        shares=1,
        saves=2,
        avg_watch_seconds=31.5,
        full_watch_ratio=0.12,
    )
    return PerformanceMetrics(**{**fields, **overrides})


def reddit(*posts, unavailable=()):
    return FakeRedditProxy(
        {
            "t": [
                RedditPost(
                    title=f"Post {post}",
                    url=f"https://www.reddit.com/r/t/comments/{post}/",
                    score=score,
                    num_comments=40,
                    upvote_ratio=0.95,
                )
                for post, score in posts
            ]
        },
        unavailable_urls={
            f"https://www.reddit.com/r/t/comments/{post}/" for post in unavailable
        },
    )


def build(history, source, reddit_proxy, *, at=NOW, progress=None):
    lines = [] if progress is None else progress

    async def record_line(text):
        lines.append(text)

    return PerformanceCollection(
        source=source,
        discovery=RedditStoryDiscovery(
            reddit=reddit_proxy,
            llm=None,
            evaluation=EvaluationConfig(subreddits=["t"]),
            now=lambda: at,
        ),
        history=history,
        config=CollectionConfig(lookback_days=30, max_gap_hours=12),
        progress=record_line,
        now=lambda: at,
    )


def contents(history, record_ids):
    """Everything the history holds about these records."""
    return (
        history.collections(),
        [
            (
                history.video_record(r),
                history.reddit_snapshots(r),
                history.performance_snapshots(r),
            )
            for r in record_ids
        ],
    )


@pytest.mark.asyncio
async def test_published_videos_get_a_snapshot_and_their_tiktok_id(history):
    first = seed(history, "A vizinha e o bolo", post="p1")
    second = seed(
        history, "O chefe e o email", post="p2", slot=SLOT + timedelta(hours=3)
    )
    source = FakePerformanceSource(
        [
            tiktok("v1", "A vizinha e o bolo"),
            tiktok("v2", "O chefe e o email", posted=SLOT + timedelta(hours=3)),
        ],
        {"v1": analytics(views=900), "v2": analytics(views=40)},
    )
    lines = []

    report = await build(
        history, source, reddit(("p1", 120), ("p2", 7)), progress=lines
    ).collect()

    assert (report.collection.matched, report.collection.unmatched) == (2, 0)
    assert history.performance_snapshots(first) == [
        PerformanceSnapshot(
            taken_at=NOW,
            tiktok_video_id="v1",
            metrics=analytics(views=900),
            tiktok_created_at=SLOT + timedelta(minutes=2),
        )
    ]
    assert history.video_record(first).tiktok_video_id == "v1"
    assert history.video_record(second).tiktok_video_id == "v2"
    assert source.since == [NOW - timedelta(days=30)]
    assert source.closed == 1
    assert lines == [
        "🔎 2 vídeos no Studio, 2 registros publicados",
        "✅ 2 casados, 0 sem par, 0 ambíguos",
    ]


@pytest.mark.asyncio
async def test_a_second_collection_adds_snapshots_and_keeps_the_first(history):
    record_id = seed(history, "A vizinha e o bolo")
    videos = [tiktok("v1", "A vizinha e o bolo")]

    await build(
        history,
        FakePerformanceSource(videos, {"v1": analytics(views=500)}),
        reddit(("p1", 120)),
    ).collect()
    await build(
        history,
        FakePerformanceSource(videos, {"v1": analytics(views=800)}),
        reddit(("p1", 180)),
        at=LATER,
    ).collect()

    assert [
        (s.taken_at, s.metrics.views) for s in history.performance_snapshots(record_id)
    ] == [(NOW, 500), (LATER, 800)]
    assert [s.score for s in history.reddit_snapshots(record_id)] == [100, 120, 180]
    assert len(history.collections()) == 2


@pytest.mark.asyncio
async def test_a_video_without_a_record_is_reported_and_nothing_is_attached(history):
    record_id = seed(history, "A vizinha e o bolo")
    by_hand = tiktok("v9", "Postado à mão", posted=SLOT + timedelta(days=1))
    source = FakePerformanceSource([by_hand], {})
    lines = []

    report = await build(history, source, reddit(("p1", 120)), progress=lines).collect()

    assert report.unmatched_videos == [by_hand]
    assert report.collection.matched == 0
    assert source.asked == []
    assert history.performance_snapshots(record_id) == []
    assert history.video_record(record_id).tiktok_video_id is None
    posted = by_hand.created_at.astimezone().strftime("%d/%m %H:%M")
    assert lines[-1] == f"❓ Sem par: Postado à mão ({posted}) — TikTok v9"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [{"fail_fetch": True}, {"fail_metrics_for": {"v1"}}],
    ids=["session-expired", "layout-changed"],
)
async def test_a_studio_that_fails_leaves_the_history_as_it_was(history, failure):
    record_id = seed(history, "A vizinha e o bolo")
    source = FakePerformanceSource([tiktok("v1", "A vizinha e o bolo")], {}, **failure)
    before = contents(history, [record_id])

    with pytest.raises((TikTokSessionExpiredError, TikTokStudioLayoutError)):
        await build(history, source, reddit(("p1", 120))).collect()

    assert contents(history, [record_id]) == before
    assert source.closed == 1


@pytest.mark.asyncio
async def test_a_reddit_that_is_down_leaves_the_history_as_it_was(history):
    record_id = seed(history, "A vizinha e o bolo")
    before = contents(history, [record_id])
    source = FakePerformanceSource(
        [tiktok("v1", "A vizinha e o bolo")], {"v1": analytics()}
    )

    # A post the fake proxy does not know raises KeyError: not "post gone".
    with pytest.raises(KeyError):
        await build(history, source, reddit()).collect()

    assert contents(history, [record_id]) == before


@pytest.mark.asyncio
async def test_a_caption_on_two_records_far_from_the_post_time_is_ambiguous(history):
    older = seed(history, "Mesma história", post="p1", slot=SLOT - timedelta(days=2))
    newer = seed(history, "Mesma história", post="p1", slot=SLOT - timedelta(days=1))
    video = tiktok("v1", "Mesma história")
    lines = []

    report = await build(
        history,
        FakePerformanceSource([video], {"v1": analytics()}),
        reddit(("p1", 120)),
        progress=lines,
    ).collect()

    assert report.ambiguous == [(video, [older, newer])]
    assert report.collection.ambiguous == 1
    assert history.performance_snapshots(older) == []
    assert history.performance_snapshots(newer) == []
    assert lines[-1].startswith("⚠️ Ambíguo: Mesma história (")
    assert lines[-1].endswith(f"— TikTok v1 — registros {older}, {newer}")


@pytest.mark.asyncio
async def test_each_matched_record_gets_a_reddit_snapshot_even_when_the_post_is_gone(
    history,
):
    kept = seed(history, "A vizinha e o bolo", post="p1")
    gone = seed(history, "O chefe e o email", post="p2", slot=SLOT + timedelta(hours=3))
    source = FakePerformanceSource(
        [
            tiktok("v1", "A vizinha e o bolo"),
            tiktok("v2", "O chefe e o email", posted=SLOT + timedelta(hours=3)),
        ],
        {"v1": analytics(), "v2": analytics()},
    )

    report = await build(
        history, source, reddit(("p1", 120), unavailable=["p2"])
    ).collect()

    assert report.collection.reddit_refreshed == 2
    assert history.reddit_snapshots(kept) == [
        FOUND,
        RedditSnapshot(
            taken_at=NOW,
            source="collection",
            score=120,
            num_comments=40,
            upvote_ratio=0.95,
        ),
    ]
    assert history.reddit_snapshots(gone)[1] == RedditSnapshot(
        taken_at=NOW,
        source="collection",
        score=None,
        num_comments=None,
        upvote_ratio=None,
        available=False,
    )


@pytest.mark.asyncio
async def test_the_parts_of_a_story_read_their_post_once(history):
    first = seed(history, "A vizinha e o bolo — parte 1", post="p1")
    second = seed(
        history,
        "A vizinha e o bolo — parte 2",
        post="p1",
        slot=SLOT + timedelta(hours=3),
    )
    proxy = reddit(("p1", 120))
    source = FakePerformanceSource(
        [
            tiktok("v1", "A vizinha e o bolo — parte 1"),
            tiktok(
                "v2", "A vizinha e o bolo — parte 2", posted=SLOT + timedelta(hours=3)
            ),
        ],
        {"v1": analytics(), "v2": analytics()},
    )

    await build(history, source, proxy).collect()

    assert proxy.fetched == ["https://www.reddit.com/r/t/comments/p1/"]
    assert history.reddit_snapshots(first)[1].score == 120
    assert history.reddit_snapshots(second)[1].score == 120


@pytest.mark.asyncio
async def test_an_assigned_video_is_matched_by_id_on_the_next_collection(history):
    record_id = seed(history, "A vizinha e o bolo")
    # TikTok shows a caption edited by hand: no caption match.
    edited = TikTokVideoStats(
        video_id="v1",
        description="Editado no app" + TAGS,
        created_at=SLOT,
        metrics=PerformanceMetrics(views=1),
    )
    first = await build(
        history,
        FakePerformanceSource([edited], {"v1": analytics()}),
        reddit(("p1", 120)),
    ).collect()

    build(history, FakePerformanceSource([], {}), reddit()).assign("v1", record_id)
    second = await build(
        history,
        FakePerformanceSource([edited], {"v1": analytics()}),
        reddit(("p1", 120)),
        at=LATER,
    ).collect()

    assert first.unmatched_videos == [edited]
    assert second.unmatched_videos == []
    assert second.collection.matched == 1
    assert [s.tiktok_video_id for s in history.performance_snapshots(record_id)] == [
        "v1"
    ]


@pytest.mark.asyncio
async def test_a_metric_the_analytics_does_not_give_stays_empty(history):
    record_id = seed(history, "A vizinha e o bolo")
    source = FakePerformanceSource(
        [tiktok("v1", "A vizinha e o bolo")],
        {"v1": analytics(avg_watch_seconds=None, full_watch_ratio=None)},
    )

    await build(history, source, reddit(("p1", 120))).collect()

    metrics = history.performance_snapshots(record_id)[0].metrics
    assert metrics.avg_watch_seconds is None
    assert metrics.full_watch_ratio is None
    assert metrics.views == 500


@pytest.mark.asyncio
async def test_lookback_days_from_the_caller_overrides_the_config(history):
    source = FakePerformanceSource([], {})

    report = await build(history, source, reddit()).collect(lookback_days=7)

    assert source.since == [NOW - timedelta(days=7)]
    assert report.collection.lookback_days == 7
