"""What the daily run leaves in the history, mode by mode (US1).

The same fakes as ``test_daily_run.py``; the history is the in-memory store and
the SQLite one on a temporary file, and both must end up the same.
"""

import dataclasses
import datetime

import pytest

from src.capabilities.writing import WriterContentBlockedError, WriterError
from src.entities.history import ModelGrade, ProductionRecipe, RedditSnapshot
from src.entities.reddit_post import RedditPost
from src.entities.story_candidate import EvaluatedStory, ExplorationFit
from src.entities.tuning import ExplorationPlan
from src.flows import daily_run as daily_run_module
from src.storage import HistoryError, SqliteHistoryStore
from tests.fakes.exploration import FakeExplorationSource
from tests.fakes.memory_history import InMemoryHistoryStore
from tests.fakes.memory_store import InMemoryRunStore
from tests.fakes.proxies import FakeSpeechProxy
from tests.fakes.publisher import FakePublisher
from tests.fakes.renderer import EchoRenderer
from tests.flows.test_daily_run import NOW, ScriptedWriter, build
from tests.proxies.test_evaluate_exploration import experiment

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
RECIPE = ProductionRecipe(
    story_prompt_version="story123",
    grading_prompt_version="grade456",
    writer_model="openrouter/writer",
    grader_model="openrouter/grader",
    rendering_strategy="narration-over-footage",
    speech_provider="edge-tts",
    speech_rate=1.5,
    narrator_gender="",
    voice_id="",
)
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


class GenderByTitle(ScriptedWriter):
    """Narrates the titles it is given with a female voice, the rest male."""

    def __init__(self, female_titles):
        super().__init__()
        self._female = set(female_titles)

    async def write(self, origin, **kwargs):
        story = await super().write(origin, **kwargs)
        gender = "female" if origin.title in self._female else "male"
        return dataclasses.replace(story, resolved_gender=gender)


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
    # Without a speech proxy the voice stays empty; the gender is the story's.
    assert first.recipe == dataclasses.replace(
        ProductionRecipe.empty(), narrator_gender="male"
    )
    assert first.duration_seconds == 1.0
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
async def test_the_next_day_reuses_the_paths_and_publish_only_finds_its_videos(
    tmp_path, history
):
    """The bot writes to output/daily every day, over yesterday's files."""
    yesterday = flow_over(tmp_path, history)
    await yesterday.run(count=1, output_dir=yesterday.output_dir)
    today = flow_over(tmp_path, history)
    today.discovery.results = graded_candidates(3)[1:]

    await today.generate(count=1, output_dir=today.output_dir)
    await today.publish(today.store.load_manifests(today.output_dir))

    (record,) = records(history, today)
    assert record.post_url == "url-2"
    assert [a.status for a in history.publish_attempts(record.id)] == ["scheduled"]
    assert [a.status for a in history.publish_attempts(record.id - 1)] == ["scheduled"]


@pytest.mark.asyncio
async def test_each_record_carries_the_recipe_with_its_story_voice(tmp_path, history):
    flow = flow_over(
        tmp_path,
        history,
        writer=GenderByTitle(female_titles={"Auto 2"}),
        recipe=RECIPE,
        speech=FakeSpeechProxy(),
    )

    await flow.generate(count=2, output_dir=flow.output_dir)

    male, female = records(history, flow)
    assert male.recipe == dataclasses.replace(
        RECIPE, narrator_gender="male", voice_id="fake-male-pt"
    )
    assert female.recipe == dataclasses.replace(
        RECIPE, narrator_gender="female", voice_id="fake-female-pt"
    )
    assert male.duration_seconds > 0


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


# --------------------------------------------------------------------------
# What each video was made for (feature 006, M4)
# --------------------------------------------------------------------------

OPEN_PLAN = ExplorationPlan(
    cycle=2, share=0.25, min_fit=75, experiments=[experiment("E001")]
)


def explored_candidates() -> list[EvaluatedStory]:
    first, second, third = graded_candidates(3)
    return [
        dataclasses.replace(first, exploration=ExplorationFit("E001", 88.0, "serve")),
        dataclasses.replace(second, exploration=ExplorationFit(None, 0.0, "")),
        # Only the exploration grade brought it in: below "Boa".
        dataclasses.replace(
            third,
            evaluation={**EVALUATION, "nota_geral": 45.0, "veredito": "Mediana"},
            exploration=ExplorationFit("E001", 97.0, "serve bem"),
        ),
    ]


@pytest.mark.asyncio
async def test_each_record_carries_the_exploration_grade_and_the_cycle(
    tmp_path, history
):
    source = FakeExplorationSource(OPEN_PLAN)
    flow = flow_over(tmp_path, history, exploration=source)
    flow.discovery.results = explored_candidates()

    await flow.generate(count=3, output_dir=flow.output_dir)

    assert flow.discovery.explored == [(["E001"], 75)]
    served, unserved = records(history, flow)
    assert (served.goal, served.exploration_experiment) == ("base", "E001")
    assert (served.exploration_fit, served.cycle) == (88.0, 2)
    assert (unserved.goal, unserved.exploration_experiment) == ("base", None)
    assert (unserved.exploration_fit, unserved.cycle) == (0.0, 2)
    # Until the run keeps slots for experiments, a story the exploration grade
    # alone brought in is not made, and the day's target does not grow for it.
    summary = history.run_summary(served.run_id)
    assert (summary.candidates_found, summary.target) == (2, 2)


@pytest.mark.asyncio
async def test_without_a_plan_the_record_is_base_with_no_grade_nor_cycle(
    tmp_path, history
):
    flow = flow_over(tmp_path, history)

    await flow.generate(count=1, output_dir=flow.output_dir)

    (made,) = records(history, flow)
    assert made.goal == "base"
    assert (made.exploration_experiment, made.exploration_fit, made.cycle) == (
        None,
        None,
        None,
    )
    assert flow.discovery.explored == [([], 70)]


@pytest.mark.asyncio
async def test_publish_only_never_reads_the_plan(tmp_path, history):
    source = FakeExplorationSource(OPEN_PLAN)
    flow = flow_over(tmp_path, history, exploration=source)
    await flow.generate(count=1, output_dir=flow.output_dir)
    reads = source.reads

    await flow.publish(flow.store.load_manifests(flow.output_dir))

    assert source.reads == reads == 1
