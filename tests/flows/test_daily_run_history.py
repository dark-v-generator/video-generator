"""What the daily run leaves in the history, mode by mode (US1).

The same fakes as ``test_daily_run.py``; the history is the in-memory store and
the SQLite one on a temporary file, and both must end up the same.
"""

import datetime

import pytest

from src.capabilities.writing import WriterContentBlockedError, WriterError
from src.entities.history import ModelGrade, ProductionRecipe, RedditSnapshot
from src.entities.reddit_post import RedditPost
from src.entities.story_candidate import EvaluatedStory
from src.flows import daily_run as daily_run_module
from src.storage import HistoryError, SqliteHistoryStore
from tests.fakes.memory_history import InMemoryHistoryStore
from tests.fakes.memory_store import InMemoryRunStore
from tests.fakes.publisher import FakePublisher
from tests.fakes.renderer import EchoRenderer
from tests.flows.test_daily_run import NOW, ScriptedWriter, build

UTC = datetime.timezone.utc
LATER = NOW + datetime.timedelta(hours=1)
POSTED = datetime.datetime(2026, 5, 4, 20, 0, tzinfo=UTC)

EVALUATION = {
    "resumo": "summary",
    "notas": {
        "retencao": {"nota": 80, "justificativa": "not recorded"},
        "qualidade": {"nota": 70, "justificativa": "not recorded"},
        "viralizacao": {"nota": 60, "justificativa": "not recorded"},
        "adequacao_tiktok": {"nota": 90, "justificativa": "not recorded"},
        "gancho": {"nota": 50, "justificativa": "not recorded"},
    },
    "nota_geral": 70.0,
    "veredito": "Boa",
}
NO_SKIPS = {
    "content_filter": 0,
    "script": 0,
    "render": 0,
    "publish": 0,
    "not_needed": 0,
}


def graded_candidates(n: int) -> list[EvaluatedStory]:
    return [
        EvaluatedStory(
            post=RedditPost(
                title=f"Auto {i}",
                content="body",
                community="r/t",
                author=f"author{i}",
                url=f"url-{i}",
                score=100 * i,
                num_comments=10 * i,
                upvote_ratio=0.9,
                created_utc=POSTED.timestamp(),
            ),
            deterministic_score=0.5,
            evaluation=EVALUATION,
        )
        for i in range(1, n + 1)
    ]


@pytest.fixture(params=["memory", "sqlite"])
def history(request, tmp_path):
    if request.param == "memory":
        return InMemoryHistoryStore()
    return SqliteHistoryStore(str(tmp_path / "history.sqlite"))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def sleep(delay):
        return None

    monkeypatch.setattr(daily_run_module.asyncio, "sleep", sleep)


def flow_over(tmp_path, history, *, n=3, **kw):
    flow = build(tmp_path, n=n, history=history, **kw)
    flow.discovery.results = graded_candidates(n)
    return flow


def records(history, flow) -> list:
    """The run's records, in the order the videos were written."""
    videos = flow.store.load_manifests(flow.output_dir)
    return [history.find_record_by_video_path(v.video_path) for v in videos]


class RenderFailsFor(EchoRenderer):
    def __init__(self, title):
        super().__init__()
        self._title = title

    async def render(self, story, *, low_quality=False):
        if story.origin.title == self._title:
            raise RuntimeError("render failed")
        return await super().render(story, low_quality=low_quality)


class RecordsFail(InMemoryHistoryStore):
    def add_video_record(self, record, discovery_signals):
        raise HistoryError("disk I/O error")


class AttemptsFail(InMemoryHistoryStore):
    def add_publish_attempt(self, record_id, attempt):
        raise HistoryError("disk I/O error")


@pytest.mark.asyncio
async def test_each_video_gets_a_record_with_signals_grade_and_attempt(
    tmp_path, history
):
    flow = flow_over(tmp_path, history)

    await flow.run(count=2, output_dir=flow.output_dir)

    first, second = records(history, flow)
    assert (first.title, first.post_url, second.post_url) == (
        "Auto 1",
        "url-1",
        "url-2",
    )
    assert (first.community, first.author, first.language) == ("r/t", "author1", "pt")
    assert first.post_created_utc == POSTED
    assert (first.part_index, first.part_count, first.imported) == (1, 1, False)
    assert first.grade == ModelGrade(70.0, "Boa", 80, 70, 60, 90, 50)
    assert first.deterministic_score == 0.5
    assert first.recipe == ProductionRecipe.empty()
    assert first.duration_seconds is None
    assert first.hashtags == ["reddit", "historia", "fyp"]
    assert history.reddit_snapshots(first.id) == [
        RedditSnapshot(
            taken_at=NOW.astimezone(UTC),
            source="discovery",
            score=100,
            num_comments=10,
            upvote_ratio=0.9,
        )
    ]
    (attempt,) = history.publish_attempts(first.id)
    assert attempt.status == "scheduled"
    assert attempt.scheduled_at == datetime.datetime(2026, 5, 5, 12, 0).astimezone(UTC)
    assert attempt.publish_result == "https://www.tiktok.com/@fake/video/1"
    assert first.run_id == second.run_id is not None


@pytest.mark.asyncio
async def test_a_three_part_story_leaves_three_sibling_records(tmp_path, history):
    flow = flow_over(tmp_path, history, writer=ScriptedWriter(parts=3))

    await flow.run(count=1, output_dir=flow.output_dir)

    parts = records(history, flow)
    assert [(r.part_index, r.part_count) for r in parts] == [(1, 3), (2, 3), (3, 3)]
    assert {r.post_url for r in parts} == {"url-1"}
    assert [r.title for r in parts] == [
        "Auto 1 - Parte 1",
        "Auto 1 - Parte 2",
        "Auto 1 - Parte 3",
    ]
    for record in parts:
        assert [a.status for a in history.publish_attempts(record.id)] == ["scheduled"]
    assert history.run_summary(parts[0].run_id).produced == 3


@pytest.mark.asyncio
async def test_a_failed_publish_and_a_later_success_share_the_record(tmp_path, history):
    store = InMemoryRunStore()
    first = flow_over(
        tmp_path, history, n=1, store=store, publisher=FakePublisher(fail_on={1})
    )
    await first.run(count=1, output_dir=first.output_dir)

    retry = flow_over(tmp_path, history, n=1, store=store)
    retry.now = lambda: LATER
    await retry.publish(store.load_manifests(first.output_dir))

    (record,) = records(history, first)
    failed, scheduled = history.publish_attempts(record.id)
    assert (failed.status, failed.attempted_at) == ("failed", NOW.astimezone(UTC))
    assert failed.error == "publisher failed on call 1"
    assert (scheduled.status, scheduled.attempted_at) == (
        "scheduled",
        LATER.astimezone(UTC),
    )
    assert history.find_record_by_video_path(record.video_path).id == record.id


@pytest.mark.asyncio
async def test_generate_only_leaves_records_that_publish_only_completes(
    tmp_path, history
):
    store = InMemoryRunStore()
    generate = flow_over(tmp_path, history, n=1, store=store, publisher=None)
    await generate.generate(count=1, output_dir=generate.output_dir)

    (record,) = records(history, generate)
    assert history.publish_attempts(record.id) == []
    summary = history.run_summary(record.run_id)
    assert (summary.mode, summary.produced, summary.scheduled) == ("generate", 1, 0)

    publish = flow_over(tmp_path, history, n=1, store=store)
    publish.now = lambda: LATER
    await publish.publish(store.load_manifests(generate.output_dir))

    assert [a.status for a in history.publish_attempts(record.id)] == ["scheduled"]
    assert records(history, generate) == [
        history.find_record_by_video_path(record.video_path)
    ]
    summary = history.run_summary(record.run_id + 1)
    assert (summary.mode, summary.requested, summary.target) == ("publish", 1, 1)
    assert (summary.produced, summary.scheduled) == (0, 1)


@pytest.mark.asyncio
async def test_publish_only_of_a_video_from_before_the_history_makes_a_minimal_record(
    tmp_path, history
):
    store = InMemoryRunStore()
    generate = flow_over(tmp_path, history, n=1, store=store, publisher=None)
    generate.history = InMemoryHistoryStore()  # rendered before the history existed
    await generate.generate(count=1, output_dir=generate.output_dir)

    publish = flow_over(tmp_path, history, n=1, store=store)
    await publish.publish(store.load_manifests(generate.output_dir))

    (video,) = store.load_manifests(generate.output_dir)
    record = history.find_record_by_video_path(video.video_path)
    assert (record.title, record.post_url, record.imported) == ("Auto 1", "url-1", True)
    assert record.grade is None and record.recipe is None
    assert history.reddit_snapshots(record.id) == []
    assert [a.status for a in history.publish_attempts(record.id)] == ["scheduled"]


@pytest.mark.asyncio
async def test_blocked_and_unrendered_stories_stay_out_and_are_counted(
    tmp_path, history
):
    writer = ScriptedWriter({"Auto 1": [WriterContentBlockedError("filter")]})
    flow = flow_over(
        tmp_path, history, writer=writer, renderer=RenderFailsFor("Auto 2")
    )

    await flow.run(count=1, output_dir=flow.output_dir)

    (record,) = records(history, flow)
    assert record.post_url == "url-3"
    summary = history.run_summary(record.run_id)
    assert summary.skipped == {**NO_SKIPS, "content_filter": 1, "render": 1}


@pytest.mark.asyncio
async def test_the_run_summary_counts_what_happened(tmp_path, history):
    flow = flow_over(
        tmp_path,
        history,
        n=5,
        writer=ScriptedWriter({"Auto 1": [WriterError("bad json")]}),
        publisher=FakePublisher(fail_on={1}),
    )

    await flow.run(count=2, output_dir=flow.output_dir)

    summary = history.run_summary(1)
    assert summary.started_at == NOW.astimezone(UTC)
    assert summary.finished_at == NOW.astimezone(UTC)
    assert (summary.mode, summary.requested, summary.target) == ("run", 2, 2)
    assert (summary.candidates_found, summary.produced, summary.scheduled) == (5, 3, 2)
    # Auto 1 has a bad script, Auto 2 is not taken by TikTok, Auto 3 and 4 are
    # scheduled, and Auto 5 is left over.
    assert summary.skipped == {**NO_SKIPS, "script": 1, "publish": 1, "not_needed": 1}
    assert summary.stopped_reason == ""


@pytest.mark.asyncio
async def test_a_failed_search_is_summarised_without_records(tmp_path, history):
    flow = flow_over(tmp_path, history)
    flow.discovery.error = RuntimeError("reddit down")

    await flow.run(count=2, output_dir=flow.output_dir)

    summary = history.run_summary(1)
    assert summary.stopped_reason == "discovery_failed"
    assert summary.finished_at is not None
    assert (summary.candidates_found, summary.produced) == (0, 0)
    assert history.find_record_by_video_path(f"{flow.output_dir}/story_01.mp4") is None


@pytest.mark.asyncio
async def test_a_day_without_candidates_is_summarised(tmp_path, history):
    flow = flow_over(tmp_path, history, n=0)

    await flow.generate(count=2, output_dir=flow.output_dir)

    summary = history.run_summary(1)
    assert (summary.mode, summary.stopped_reason) == ("generate", "no_candidates")
    assert summary.skipped == NO_SKIPS


@pytest.mark.asyncio
async def test_a_record_that_cannot_be_written_stops_the_run(tmp_path):
    history = RecordsFail()
    flow = flow_over(tmp_path, history)

    with pytest.raises(HistoryError, match="disk I/O error"):
        await flow.run(count=2, output_dir=flow.output_dir)

    # The manifest was written first; the run never finished.
    assert len(flow.store.load_manifests(flow.output_dir)) == 1
    assert flow.publisher.calls == []
    assert history.run_summary(1).finished_at is None


@pytest.mark.asyncio
async def test_an_attempt_that_cannot_be_written_is_not_a_publish_failure(tmp_path):
    history = AttemptsFail()
    flow = flow_over(tmp_path, history)

    with pytest.raises(HistoryError, match="disk I/O error"):
        await flow.run(count=2, output_dir=flow.output_dir)

    # The publish log row is written before the history, as it always was.
    assert [e.status for e in flow.store.log] == ["scheduled"]
    assert len(flow.publisher.calls) == 1
    assert history.run_summary(1).finished_at is None
