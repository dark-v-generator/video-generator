"""The daily run's decisions, mode by mode, with every capability faked.

No network and no model: discovery, writer, renderer, publisher and store are
all stand-ins, so what is under test is only ``DailyRun`` itself.
"""

import dataclasses
import datetime
import os

import pytest

from src.capabilities.publishing import HashtagSuggester
from src.capabilities.writing import (
    WriterContentBlockedError,
    WriterError,
    WriterTransientError,
)
from src.entities.configs.flows import DailyRunConfig
from src.entities.generated_video import GeneratedVideo
from src.entities.language import Language
from src.entities.reddit_post import RedditPost
from src.entities.story import StoryOrigin, StoryPart
from src.entities.story_candidate import EvaluatedStory
from src.flows import daily_run as daily_run_module
from src.flows.daily_run import DailyRun
from src.flows.publish_slots import next_publish_slot
from src.storage import FileRunStore, PublishLogEntry
from tests.fakes.memory_store import InMemoryRunStore
from tests.fakes.proxies import FakeLLMProxy
from tests.fakes.publisher import FakePublisher
from tests.fakes.renderer import EchoRenderer
from tests.fakes.writer import EchoStoryWriter

NOW = datetime.datetime(2026, 5, 5, 9, 0)
SLOTS = ["12:00", "18:00", "19:00", "20:00"]


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


def candidates(n: int) -> list[EvaluatedStory]:
    return [
        EvaluatedStory(
            post=RedditPost(
                title=f"Auto {i}", content="body", community="r/t", url=f"url-{i}"
            ),
            evaluation={"resumo": f"summary {i}"},
        )
        for i in range(1, n + 1)
    ]


class FakeDiscovery:
    def __init__(self, results):
        self.results = results
        self.error = None
        self.excluded = []
        self.fetched = []

    async def find_best_stories(self, *, language, exclude_urls=None, **_):
        self.excluded.append(exclude_urls)
        if self.error is not None:
            raise self.error
        return self.results

    def fetch(self, url):
        self.fetched.append(url)
        title = next(c.post.title for c in self.results if c.post.url == url)
        return StoryOrigin.from_post(RedditPost(title=title, content="body", url=url))


class ScriptedWriter(EchoStoryWriter):
    """Raises the scripted errors for a title, one per call, then writes."""

    def __init__(self, errors=None, parts=1, hashtags=None):
        super().__init__()
        self._errors = {k: list(v) for k, v in (errors or {}).items()}
        self._parts = parts
        self._hashtags = hashtags

    async def write(self, origin, **kwargs):
        errors = self._errors.get(origin.title)
        if errors:
            raise errors.pop(0)
        story = await super().write(origin, **kwargs)
        parts = [
            StoryPart(index=i, text=f"parte {i}") for i in range(1, self._parts + 1)
        ]
        return dataclasses.replace(story, parts=parts, hashtags=self._hashtags)


class FailingRenderer(EchoRenderer):
    async def render(self, story, *, low_quality=False):
        await super().render(story, low_quality=low_quality)
        raise RuntimeError("part 2 failed to render")


def build(tmp_path, *, n=3, count=4, writer=None, renderer=None, store=None, **kw):
    """A DailyRun over fakes, and the handles the tests look at."""
    messages: list[str] = []

    async def progress(text):
        messages.append(text)

    llm = FakeLLMProxy()
    flow = DailyRun(
        discovery=FakeDiscovery(candidates(n)),
        writer=writer or ScriptedWriter(),
        renderer=renderer or EchoRenderer(),
        publisher=kw.pop("publisher", FakePublisher()),
        hashtags=HashtagSuggester(llm, ["reddit"], Language.PORTUGUESE),
        store=store if store is not None else InMemoryRunStore(),
        config=DailyRunConfig(
            count=count,
            publish_slots_local=SLOTS,
            publish_min_lead_minutes=30,
            publish_hashtags=["reddit"],
            low_quality=True,
            language=Language.PORTUGUESE,
        ),
        progress=progress,
        now=lambda: NOW,
    )
    flow.messages = messages
    flow.llm = llm
    flow.output_dir = str(tmp_path / "daily")
    return flow


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    delays = []

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(daily_run_module.asyncio, "sleep", sleep)
    return delays


def slot(day, hour):
    return datetime.datetime(2026, 5, day, hour, 0)


# --------------------------------------------------------------------------
# run: discover → write → render → schedule
# --------------------------------------------------------------------------


class TestRun:
    @pytest.mark.asyncio
    async def test_discovery_skips_posts_already_scheduled(self, tmp_path):
        store = InMemoryRunStore()
        old = GeneratedVideo("v.mp4", "T", "", "already-used")
        store.append_publish_log(PublishLogEntry("scheduled", NOW, old, []))
        failed = GeneratedVideo("v.mp4", "T", "", "failed-one")
        store.append_publish_log(PublishLogEntry("failed", None, failed, []))
        flow = build(tmp_path, store=store)

        await flow.run(count=2, output_dir=flow.output_dir)

        assert flow.discovery.excluded == [{"already-used"}]
        assert [c.description for c in flow.publisher.calls] == ["Auto 1", "Auto 2"]

    @pytest.mark.asyncio
    async def test_the_target_comes_from_config_and_is_capped_by_candidates(
        self, tmp_path
    ):
        flow = build(tmp_path, n=3, count=4)

        await flow.run(output_dir=flow.output_dir)

        assert len(flow.publisher.calls) == 3
        assert flow.messages[-1] == "✅ Fluxo finalizado: 3/3 vídeos agendados."

    @pytest.mark.asyncio
    async def test_manifests_say_the_story_came_from_discovery(self, tmp_path):
        flow = build(tmp_path)

        await flow.run(count=1, output_dir=flow.output_dir)

        (manifest,) = flow.store.load_manifests(flow.output_dir)
        assert manifest.source == "auto"
        assert manifest.part is None
        assert manifest.summary == "summary 1"
        assert os.path.exists(manifest.video_path)

    @pytest.mark.asyncio
    async def test_nothing_found_says_so(self, tmp_path):
        flow = build(tmp_path, n=0)

        await flow.run(count=2, output_dir=flow.output_dir)

        assert flow.messages == [
            "🔄 Busca diária iniciada...",
            "Nenhuma história boa encontrada hoje.",
        ]

    @pytest.mark.asyncio
    async def test_discovery_failure_is_reported(self, tmp_path):
        flow = build(tmp_path)
        flow.discovery.error = RuntimeError("reddit down")

        await flow.run(count=2, output_dir=flow.output_dir)

        assert flow.messages == [
            "🔄 Busca diária iniciada...",
            "Erro ao buscar histórias: reddit down",
        ]

    @pytest.mark.asyncio
    async def test_a_transient_error_is_retried_with_backoff(self, tmp_path, no_sleep):
        errors = [WriterTransientError("429"), WriterTransientError("429")]
        flow = build(tmp_path, writer=ScriptedWriter({"Auto 1": errors}))

        await flow.run(count=1, output_dir=flow.output_dir)

        assert no_sleep == [5, 10]
        assert "#1 Gerando roteiro... (tentativa 3/3)" in flow.messages
        assert [c.description for c in flow.publisher.calls] == ["Auto 1"]

    @pytest.mark.asyncio
    async def test_a_transient_error_on_the_last_attempt_skips_the_story(
        self, tmp_path
    ):
        errors = [WriterTransientError("429")] * 3
        flow = build(tmp_path, writer=ScriptedWriter({"Auto 1": errors}))

        await flow.run(count=1, output_dir=flow.output_dir)

        assert (
            "❌ #1 Erro no roteiro: 429. Tentando outra história para completar 1."
            in flow.messages
        )
        assert [c.description for c in flow.publisher.calls] == ["Auto 2"]

    @pytest.mark.asyncio
    async def test_blocked_and_failed_scripts_skip_to_the_next_candidate(
        self, tmp_path
    ):
        writer = ScriptedWriter(
            {
                "Auto 1": [WriterContentBlockedError("filter")],
                "Auto 2": [WriterError("bad json")],
            }
        )
        flow = build(tmp_path, writer=writer)

        await flow.run(count=1, output_dir=flow.output_dir)

        assert "⚠️ #1 Bloqueado por filtro de conteúdo, pulando." in flow.messages
        assert any(
            m.startswith("❌ #2 Erro no roteiro: bad json") for m in flow.messages
        )
        assert [c.description for c in flow.publisher.calls] == ["Auto 3"]

    @pytest.mark.asyncio
    async def test_failed_publish_skips_the_story_and_keeps_the_slot(self, tmp_path):
        flow = build(tmp_path, publisher=FakePublisher(fail_on={1}))

        await flow.run(count=2, output_dir=flow.output_dir)

        assert flow.discovery.fetched == ["url-1", "url-2", "url-3"]
        calls = flow.publisher.calls
        assert [c.description for c in calls] == ["Auto 1", "Auto 2", "Auto 3"]
        # The failed attempt did not take its slot: the next story gets it.
        assert [c.schedule_at for c in calls] == [slot(5, 12), slot(5, 12), slot(5, 18)]
        assert [e.status for e in flow.store.log] == [
            "failed",
            "scheduled",
            "scheduled",
        ]
        assert flow.messages[-1] == "✅ Fluxo finalizado: 2/2 vídeos agendados."


# --------------------------------------------------------------------------
# Stories in several parts
# --------------------------------------------------------------------------


class TestMultipart:
    @pytest.mark.asyncio
    async def test_three_part_story_schedules_consecutive_slots(self, tmp_path):
        flow = build(tmp_path, writer=ScriptedWriter(parts=3))

        await flow.run(count=1, output_dir=flow.output_dir)

        calls = flow.publisher.calls
        assert [c.description for c in calls] == [
            "Auto 1 - Parte 1",
            "Auto 1 - Parte 2",
            "Auto 1 - Parte 3",
        ]
        assert [c.schedule_at for c in calls] == [slot(5, 12), slot(5, 18), slot(5, 19)]
        assert [os.path.basename(c.video_path) for c in calls] == [
            "story_01.mp4",
            "story_01_p2.mp4",
            "story_01_p3.mp4",
        ]
        assert [(e.status, e.video.part) for e in flow.store.log] == [
            ("scheduled", 1),
            ("scheduled", 2),
            ("scheduled", 3),
        ]
        # One story toward the target, and its hashtags asked for once.
        assert flow.messages[-1] == "✅ Fluxo finalizado: 1/1 vídeos agendados."
        assert flow.llm.calls == [("generate_hashtags", "Auto 1")]
        assert all(c.hashtags == ["reddit", "historia", "fyp"] for c in calls)

    @pytest.mark.asyncio
    async def test_three_part_render_failure_publishes_nothing(self, tmp_path):
        flow = build(
            tmp_path, n=1, writer=ScriptedWriter(parts=3), renderer=FailingRenderer()
        )

        await flow.run(count=1, output_dir=flow.output_dir)

        assert flow.publisher.calls == []
        assert flow.store.log == []
        assert flow.store.load_manifests(flow.output_dir) == []
        assert os.listdir(flow.output_dir) == []
        assert flow.messages[-1] == "✅ Fluxo finalizado: 0/1 vídeos agendados."

    @pytest.mark.asyncio
    async def test_a_failed_part_leaves_the_rest_and_the_next_story_follows_it(
        self, tmp_path
    ):
        flow = build(
            tmp_path,
            writer=ScriptedWriter(parts=3),
            publisher=FakePublisher(fail_on={2}),
        )

        await flow.run(count=1, output_dir=flow.output_dir)

        calls = flow.publisher.calls
        assert [c.description for c in calls] == [
            "Auto 1 - Parte 1",
            "Auto 1 - Parte 2",
            "Auto 2 - Parte 1",
            "Auto 2 - Parte 2",
            "Auto 2 - Parte 3",
        ]
        # Part 1 of the first story kept 12:00; the next story starts after it.
        assert [c.schedule_at for c in calls] == [
            slot(5, 12),
            slot(5, 18),
            slot(5, 18),
            slot(5, 19),
            slot(5, 20),
        ]
        assert flow.messages[-1] == "✅ Fluxo finalizado: 1/1 vídeos agendados."

    @pytest.mark.asyncio
    async def test_hashtags_written_with_the_story_skip_the_model(self, tmp_path):
        writer = ScriptedWriter(parts=2, hashtags=["#Traição", "fyp"])
        flow = build(tmp_path, writer=writer)

        await flow.run(count=1, output_dir=flow.output_dir)

        assert flow.llm.calls == []
        assert [c.hashtags for c in flow.publisher.calls] == [
            ["reddit", "Traicao", "fyp"],
            ["reddit", "Traicao", "fyp"],
        ]


# --------------------------------------------------------------------------
# generate: no publishing at all
# --------------------------------------------------------------------------


class TestGenerateOnly:
    @pytest.mark.asyncio
    async def test_generates_without_a_publisher(self, tmp_path):
        flow = build(tmp_path, publisher=None)

        videos = await flow.generate(count=1, output_dir=flow.output_dir)

        assert [video.source for video in videos] == ["auto"]
        assert flow.discovery.excluded == [set()]
        assert flow.store.log == []
        assert flow.messages[-1] == "✅ Geração finalizada: 1/1 vídeos prontos."

    @pytest.mark.asyncio
    async def test_a_three_part_story_writes_one_video_per_part(self, tmp_path):
        store = FileRunStore(str(tmp_path / "log.csv"))
        flow = build(tmp_path, writer=ScriptedWriter(parts=3), store=store)

        videos = await flow.generate(count=1, output_dir=flow.output_dir)

        assert sorted(os.listdir(flow.output_dir)) == [
            "story_01.json",
            "story_01.mp4",
            "story_01_p2.json",
            "story_01_p2.mp4",
            "story_01_p3.json",
            "story_01_p3.mp4",
        ]
        assert [(v.part, v.title) for v in store.load_manifests(flow.output_dir)] == [
            (1, "Auto 1 - Parte 1"),
            (2, "Auto 1 - Parte 2"),
            (3, "Auto 1 - Parte 3"),
        ]
        assert [video.part for video in videos] == [1, 2, 3]
        assert "#1 Parte 3 gerada" in flow.messages
        # The target counts stories, not videos.
        assert flow.messages[-1] == "✅ Geração finalizada: 1/1 vídeos prontos."


# --------------------------------------------------------------------------
# publish: videos generated earlier
# --------------------------------------------------------------------------


def generated(tmp_path, *titles) -> list[GeneratedVideo]:
    videos = []
    for i, title in enumerate(titles, start=1):
        path = tmp_path / f"story_{i:02d}.mp4"
        path.write_bytes(b"video")
        videos.append(GeneratedVideo(str(path), title, "s", f"url-{i}"))
    return videos


class TestPublishFromDirectory:
    @pytest.mark.asyncio
    async def test_videos_are_scheduled_in_order_and_consecutively(self, tmp_path):
        flow = build(tmp_path)

        await flow.publish(generated(tmp_path, "First", "Second"))

        first, second = flow.publisher.calls
        assert (first.description, second.description) == ("First", "Second")
        assert second.schedule_at == next_publish_slot(
            after=first.schedule_at, slot_times=SLOTS, min_lead_minutes=30, _now=NOW
        )

    @pytest.mark.asyncio
    async def test_a_failed_video_is_logged_and_the_next_one_still_goes(self, tmp_path):
        flow = build(tmp_path, publisher=FakePublisher(fail_on={1}))

        await flow.publish(generated(tmp_path, "First", "Second"))

        assert [c.description for c in flow.publisher.calls] == ["First", "Second"]
        assert [e.status for e in flow.store.log] == ["failed", "scheduled"]
        assert flow.messages[1] == "❌ [#1 — First] Erro: publisher failed on call 1"
        assert flow.messages[-1] == "🏁 Agendamento concluído."

    @pytest.mark.asyncio
    async def test_no_videos_says_so(self, tmp_path):
        flow = build(tmp_path)

        await flow.publish([])

        assert flow.messages == ["Nenhum vídeo para publicar."]


# --------------------------------------------------------------------------
# The store is a seam: memory and files record the same run (SC-006)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_memory_and_file_stores_record_the_same_run(tmp_path):
    def run_with(store, where):
        return build(
            where,
            writer=ScriptedWriter(parts=2),
            publisher=FakePublisher(fail_on={3}),
            store=store,
        )

    memory = run_with(InMemoryRunStore(), tmp_path / "memory")
    files = run_with(
        FileRunStore(str(tmp_path / "files" / "log.csv")), tmp_path / "files"
    )

    for flow in (memory, files):
        await flow.run(count=2, output_dir=flow.output_dir)

    def relative(flow, videos):
        return [
            dataclasses.replace(
                v, video_path=os.path.relpath(v.video_path, flow.output_dir)
            )
            for v in videos
        ]

    assert memory.messages == files.messages
    assert relative(memory, memory.store.load_manifests(memory.output_dir)) == relative(
        files, files.store.load_manifests(files.output_dir)
    )
    assert memory.store.scheduled_post_urls() == files.store.scheduled_post_urls()
    with open(tmp_path / "files" / "log.csv") as f:
        statuses = [line.split(",")[1] for line in f.read().splitlines()[1:]]
    assert statuses == [e.status for e in memory.store.log]
