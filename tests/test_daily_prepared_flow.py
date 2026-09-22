"""Tests for the daily job once the prepared-story queue sits in front of discovery.

The seven invariants of contracts/queue.md are exercised here against both
``run_daily_auto_publish`` and ``run_daily_generate``, with no network: the
finder, the video service, the LLM and the publisher are all fakes, and the
queue is a real ``PreparedStoryQueue`` over ``tmp_path``.
"""

import csv
import json
import os
from types import SimpleNamespace

import pytest

from bots import satisfying_bot
from src.entities.configs.bots import PreparedStoriesConfig
from src.entities.reddit_post import RedditPost
from src.entities.story_candidate import EvaluatedStory
from src.services.prepared_story_queue import PreparedStoryQueue
from src.services.reddit_video_service import PreparedStory
from src.services.text_censor import TextCensor

from tests.test_prepared_story_package import package_payload
from tests.test_prepared_story_queue import (
    other_post_url,
    write_inbox,
    write_two_part_inbox,
)

# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


class FakeService:
    def __init__(self):
        self.prepared_urls = []
        self.generated_titles = []
        self.fail_titles: set[str] = set()

    async def prepare_satisfying_story(self, *, post_url, language):
        self.prepared_urls.append(post_url)
        return PreparedStory(
            post=RedditPost(title=f"auto {post_url}", content="body", url=post_url),
            script_text="auto script",
            story_title=f"auto {post_url}",
            narrator_gender="unknown",
            resolved_gender="male",
            original_post_md="original",
        )

    async def generate_satisfying_video_from_story(
        self, prepared, *, language, low_quality
    ):
        self.generated_titles.append(prepared.story_title)
        if prepared.story_title in self.fail_titles:
            raise RuntimeError("render exploded")
        return SimpleNamespace(video=b"video", localized_title=prepared.story_title)


class FakeLLM:
    def __init__(self):
        self.hashtag_calls = []

    async def generate_hashtags(self, *, title, summary, target_language):
        self.hashtag_calls.append(title)
        return ["fyp"]


class FakePublisher:
    def __init__(self):
        self.calls = []
        self.fail_descriptions: set[str] = set()

    async def publish_video(self, *, video_path, description, hashtags, schedule_at):
        self.calls.append(
            SimpleNamespace(
                video_path=video_path,
                description=description,
                hashtags=hashtags,
                schedule_at=schedule_at,
            )
        )
        if description in self.fail_descriptions:
            raise RuntimeError("browser exploded")
        return "scheduled"


class FakeContainer:
    def __init__(self, service, llm, queue):
        self._service = service
        self._llm = llm
        self._queue = queue

    def wire(self, modules):
        return None

    def reddit_video_service(self):
        return self._service

    def llm_proxy(self):
        return self._llm

    def prepared_story_queue(self):
        return self._queue

    def text_censor(self):
        return TextCensor()


class SpyQueue:
    """Wraps a real queue and records which operations the bot reached for."""

    def __init__(self, queue: PreparedStoryQueue):
        self._queue = queue
        self.calls: list[str] = []

    @property
    def last_rejections(self):
        return self._queue.last_rejections

    def list_inbox(self):
        self.calls.append("list_inbox")
        return self._queue.list_inbox()

    def known_post_urls(self):
        self.calls.append("known_post_urls")
        return self._queue.known_post_urls()

    def mark_done(self, item, outcome):
        self.calls.append("mark_done")
        return self._queue.mark_done(item, outcome)

    def mark_failed(self, item, error):
        self.calls.append("mark_failed")
        return self._queue.mark_failed(item, error)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def auto_stories(n: int) -> list[EvaluatedStory]:
    return [
        EvaluatedStory(
            post=RedditPost(
                title=f"Auto {i}",
                content="body",
                community="r/test",
                url=f"auto-url-{i}",
            ),
            evaluation={"resumo": f"auto summary {i}"},
        )
        for i in range(1, n + 1)
    ]


@pytest.fixture
def env(monkeypatch, tmp_path):
    """Wire the bot module to fakes and return the handles the tests poke at."""
    queue_root = tmp_path / "prepared"
    real_queue = PreparedStoryQueue(str(queue_root))
    queue = SpyQueue(real_queue)

    service = FakeService()
    llm = FakeLLM()
    publisher = FakePublisher()
    messages: list[str] = []
    discovery = SimpleNamespace(calls=[], results=auto_stories(3), error=None)

    async def send_message(text):
        messages.append(text)

    async def discover_stories(subreddits=None, exclude_urls=None):
        discovery.calls.append(exclude_urls)
        if discovery.error is not None:
            raise discovery.error
        return discovery.results

    monkeypatch.setattr(satisfying_bot, "_discover_stories", discover_stories)
    monkeypatch.setattr(satisfying_bot, "container", FakeContainer(service, llm, queue))
    monkeypatch.setattr(satisfying_bot, "_build_tiktok_publisher", lambda: publisher)
    monkeypatch.setenv(
        "TIKTOK_PUBLISH_LOG_PATH", str(tmp_path / "tiktok_publish_log.csv")
    )
    monkeypatch.setattr(
        satisfying_bot,
        "bot_config",
        SimpleNamespace(
            allowed_user_ids=[1],
            low_quality=True,
            daily_auto_publish_count=4,
            publish_slots_local=["12:00", "18:00", "19:00", "20:00"],
            publish_min_lead_minutes=30,
            publish_hashtags=["reddit"],
            prepared_stories=PreparedStoriesConfig(),
        ),
    )

    return SimpleNamespace(
        queue=queue,
        queue_root=queue_root,
        service=service,
        llm=llm,
        publisher=publisher,
        messages=messages,
        discovery=discovery,
        send_message=send_message,
        output_dir=str(tmp_path / "daily"),
        publish_log=tmp_path / "tiktok_publish_log.csv",
    )


def manifests(output_dir: str) -> list[dict]:
    return [
        json.loads(open(os.path.join(output_dir, name)).read())
        for name in sorted(os.listdir(output_dir))
        if name.endswith(".json")
    ]


# --------------------------------------------------------------------------
# Invariant 1 — empty inbox behaves exactly like today
# --------------------------------------------------------------------------


class TestEmptyInbox:
    @pytest.mark.asyncio
    async def test_discovery_drives_the_run_and_only_list_inbox_is_touched(self, env):
        env.publish_log.write_text(
            "created_at,status,scheduled_at,video_path,title,post_url,hashtags,"
            "publish_result,error\n"
            "2026-09-20T10:00:00,scheduled,2026-09-20T18:00,v.mp4,T,already-used,,ok,\n"
            "2026-09-20T10:00:00,failed,,v.mp4,T,failed-one,,,boom\n"
        )

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=2, output_dir=env.output_dir
        )

        assert env.discovery.calls == [{"already-used"}]
        assert env.queue.calls == ["list_inbox", "known_post_urls"]
        assert [call.description for call in env.publisher.calls] == [
            "auto auto-url-1",
            "auto auto-url-2",
        ]

    @pytest.mark.asyncio
    async def test_messages_are_the_ones_from_before_the_queue(self, env):
        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=2, output_dir=env.output_dir
        )

        assert env.messages[0] == "🔄 Busca diária iniciada..."
        assert (
            "✅ Busca finalizada: 3 histórias disponíveis. "
            "Iniciando geração de vídeo e agendamento." in env.messages
        )
        assert "✅ Fluxo finalizado: 2/2 vídeos agendados." in env.messages
        assert not any("📦" in message for message in env.messages)

    @pytest.mark.asyncio
    async def test_manifests_say_the_story_came_from_discovery(self, env):
        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert [m["source"] for m in manifests(env.output_dir)] == ["auto"]

    @pytest.mark.asyncio
    async def test_nothing_found_keeps_the_old_message(self, env):
        env.discovery.results = []

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=2, output_dir=env.output_dir
        )

        assert env.messages == [
            "🔄 Busca diária iniciada...",
            "Nenhuma história boa encontrada hoje.",
        ]

    @pytest.mark.asyncio
    async def test_discovery_failure_keeps_the_old_message(self, env):
        env.discovery.error = RuntimeError("reddit down")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=2, output_dir=env.output_dir
        )

        assert env.messages == [
            "🔄 Busca diária iniciada...",
            "Erro ao buscar histórias: reddit down",
        ]


# --------------------------------------------------------------------------
# Invariant 2 — a full queue keeps every model out of the run
# --------------------------------------------------------------------------


class TestQueueCoversTheTarget:
    @pytest.mark.asyncio
    async def test_no_discovery_no_script_and_no_hashtag_call(self, env):
        write_inbox(str(env.queue_root), "aaa", story_title="Pacote A")
        write_inbox(str(env.queue_root), "bbb", story_title="Pacote B")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=2, output_dir=env.output_dir
        )

        assert env.discovery.calls == []
        assert env.service.prepared_urls == []
        assert env.llm.hashtag_calls == []
        assert env.service.generated_titles == ["Pacote A", "Pacote B"]

    @pytest.mark.asyncio
    async def test_title_and_script_are_used_verbatim(self, env):
        write_inbox(
            str(env.queue_root),
            "aaa",
            story_title="Título exato do operador",
            script_text="Roteiro exato do operador.",
        )

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert env.publisher.calls[0].description == "Título exato do operador"
        (manifest,) = manifests(env.output_dir)
        assert manifest["title"] == "Título exato do operador"
        assert manifest["source"] == "prepared"
        assert manifest["post_url"] == other_post_url("aaa")
        assert manifest["summary"] == package_payload()["summary"]

    @pytest.mark.asyncio
    async def test_announces_the_queue_and_names_each_prepared_script(self, env):
        write_inbox(str(env.queue_root), "aaa", story_title="Pacote A")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert "📦 1 história(s) preparada(s) na fila." in env.messages
        assert '#1 Usando roteiro preparado: "Pacote A"' in env.messages
        assert not any("Gerando roteiro" in message for message in env.messages)

    @pytest.mark.asyncio
    async def test_hashtags_from_the_package_replace_the_llm(self, env):
        write_inbox(str(env.queue_root), "aaa", hashtags=["historia", "reddit"])

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert env.llm.hashtag_calls == []
        assert env.publisher.calls[0].hashtags == ["reddit", "historia", "fyp"]

    @pytest.mark.asyncio
    async def test_package_without_hashtags_falls_back_to_the_llm(self, env):
        write_inbox(str(env.queue_root), "aaa", hashtags=None)

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert env.llm.hashtag_calls == [package_payload()["story_title"]]


# --------------------------------------------------------------------------
# Invariant 3 and 4 — a short queue
# --------------------------------------------------------------------------


class TestShortQueue:
    @pytest.mark.asyncio
    async def test_prepared_first_then_discovery_excluding_them(self, env):
        write_inbox(str(env.queue_root), "aaa", story_title="Pacote A")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=2, output_dir=env.output_dir
        )

        assert env.service.generated_titles == ["Pacote A", "auto auto-url-1"]
        (exclude,) = env.discovery.calls
        assert other_post_url("aaa") in exclude
        assert [m["source"] for m in manifests(env.output_dir)] == [
            "prepared",
            "auto",
        ]

    @pytest.mark.asyncio
    async def test_discovery_disabled_publishes_only_the_queue(self, env, monkeypatch):
        monkeypatch.setattr(
            satisfying_bot.bot_config,
            "prepared_stories",
            PreparedStoriesConfig(fill_with_discovery=False),
        )
        write_inbox(str(env.queue_root), "aaa", story_title="Pacote A")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=2, output_dir=env.output_dir
        )

        assert env.discovery.calls == []
        assert env.service.generated_titles == ["Pacote A"]
        assert "✅ Fluxo finalizado: 1/2 vídeos agendados." in env.messages

    @pytest.mark.asyncio
    async def test_queue_longer_than_the_target_stops_at_the_target(self, env):
        for post_id in ("aaa", "bbb", "ccc"):
            write_inbox(str(env.queue_root), post_id, story_title=f"Pacote {post_id}")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=2, output_dir=env.output_dir
        )

        assert env.service.generated_titles == ["Pacote aaa", "Pacote bbb"]
        assert (env.queue_root / "inbox" / "ccc.json").exists()


# --------------------------------------------------------------------------
# Invariant 5, 6, 7 — package outcomes
# --------------------------------------------------------------------------


class TestPackageOutcomes:
    @pytest.mark.asyncio
    async def test_wrong_language_fails_before_any_video_is_made(self, env):
        write_inbox(str(env.queue_root), "aaa", language="en")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert env.service.generated_titles == ["auto auto-url-1"]
        assert (env.queue_root / "failed" / "aaa.json").exists()
        error = (env.queue_root / "failed" / "aaa.error.txt").read_text()
        assert "language: package=en server=pt" in error
        assert any(
            "Pacote inválido" in message and "failed/" in message
            for message in env.messages
        )

    @pytest.mark.asyncio
    async def test_forbidden_word_fails_the_package(self, env):
        write_inbox(
            str(env.queue_root),
            "aaa",
            script_text="Ele quase me matou de raiva naquele dia.",
        )

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert (env.queue_root / "failed" / "aaa.json").exists()
        assert "matou" in (env.queue_root / "failed" / "aaa.error.txt").read_text()

    @pytest.mark.asyncio
    async def test_unparseable_file_is_reported_and_the_run_continues(self, env):
        os.makedirs(env.queue_root / "inbox", exist_ok=True)
        (env.queue_root / "inbox" / "broken.json").write_text("{not json")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert (env.queue_root / "failed" / "broken.json").exists()
        assert any("Pacote inválido" in message for message in env.messages)
        assert env.service.generated_titles == ["auto auto-url-1"]

    @pytest.mark.asyncio
    async def test_generation_failure_moves_the_package_to_failed(self, env):
        write_inbox(str(env.queue_root), "aaa", story_title="Pacote A")
        env.service.fail_titles = {"Pacote A"}

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert (env.queue_root / "failed" / "aaa.json").exists()
        assert (
            "render exploded"
            in (env.queue_root / "failed" / "aaa.error.txt").read_text()
        )

    @pytest.mark.asyncio
    async def test_publish_failure_moves_the_package_to_failed(self, env):
        write_inbox(str(env.queue_root), "aaa", story_title="Pacote A")
        env.publisher.fail_descriptions = {"Pacote A"}

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert (env.queue_root / "failed" / "aaa.json").exists()
        assert (
            "browser exploded"
            in (env.queue_root / "failed" / "aaa.error.txt").read_text()
        )

    @pytest.mark.asyncio
    async def test_success_moves_the_package_to_done_with_an_outcome(self, env):
        write_inbox(str(env.queue_root), "aaa", story_title="Pacote A")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert (env.queue_root / "done" / "aaa.json").exists()
        outcome = json.loads((env.queue_root / "done" / "aaa.outcome.json").read_text())
        assert outcome["status"] == "scheduled"
        assert outcome["scheduled_at"]
        assert outcome["hashtags"] == ["reddit", "historia", "fyp"]
        assert outcome["video_path"].endswith("story_01.mp4")
        assert outcome["manifest_path"].endswith("story_01.json")

    @pytest.mark.asyncio
    async def test_publish_log_carries_the_package_post_url(self, env):
        write_inbox(str(env.queue_root), "aaa", story_title="Pacote A")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        with open(env.publish_log, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert [row["post_url"] for row in rows] == [other_post_url("aaa")]
        assert rows[0]["status"] == "scheduled"


# --------------------------------------------------------------------------
# run_daily_generate
# --------------------------------------------------------------------------


class TestGenerateOnly:
    @pytest.mark.asyncio
    async def test_prepared_package_is_generated_and_marked_generated(self, env):
        write_inbox(str(env.queue_root), "aaa", story_title="Pacote A")

        videos = await satisfying_bot.run_daily_generate(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert [video.title for video in videos] == ["Pacote A"]
        assert [video.source for video in videos] == ["prepared"]
        assert env.publisher.calls == []

        outcome = json.loads((env.queue_root / "done" / "aaa.outcome.json").read_text())
        assert outcome["status"] == "generated"
        assert outcome["scheduled_at"] is None

    @pytest.mark.asyncio
    async def test_empty_inbox_still_discovers(self, env):
        videos = await satisfying_bot.run_daily_generate(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert [video.source for video in videos] == ["auto"]
        assert env.discovery.calls == [set()]
        assert "✅ Geração finalizada: 1/1 vídeos prontos." in env.messages

    @pytest.mark.asyncio
    async def test_generation_failure_moves_the_package_to_failed(self, env):
        write_inbox(str(env.queue_root), "aaa", story_title="Pacote A")
        env.service.fail_titles = {"Pacote A"}

        await satisfying_bot.run_daily_generate(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert (env.queue_root / "failed" / "aaa.json").exists()


# --------------------------------------------------------------------------
# T030 — dedup against the publish log
# --------------------------------------------------------------------------


class TestScheduledPostUrls:
    def test_only_scheduled_rows_count(self, tmp_path):
        path = tmp_path / "log.csv"
        path.write_text(
            "created_at,status,scheduled_at,video_path,title,post_url,hashtags,"
            "publish_result,error\n"
            "2026-09-20T10:00:00,scheduled,2026-09-20T18:00,a.mp4,A,url-a,,ok,\n"
            "2026-09-20T11:00:00,failed,,b.mp4,B,url-b,,,boom\n"
            "2026-09-20T12:00:00,scheduled,2026-09-20T19:00,c.mp4,C,url-c,,ok,\n"
        )

        assert satisfying_bot._scheduled_post_urls(str(path)) == {"url-a", "url-c"}

    def test_missing_file_is_an_empty_set(self, tmp_path):
        assert satisfying_bot._scheduled_post_urls(str(tmp_path / "nope.csv")) == set()

    def test_rows_without_a_post_url_are_skipped(self, tmp_path):
        path = tmp_path / "log.csv"
        path.write_text(
            "created_at,status,scheduled_at,video_path,title,post_url,hashtags,"
            "publish_result,error\n"
            "2026-09-20T10:00:00,scheduled,2026-09-20T18:00,a.mp4,A,,,ok,\n"
        )

        assert satisfying_bot._scheduled_post_urls(str(path)) == set()


# --------------------------------------------------------------------------
# Backwards compatibility of the manifest
# --------------------------------------------------------------------------


class TestLoadGeneratedVideos:
    def test_manifest_without_source_still_loads(self, tmp_path):
        (tmp_path / "story_01.mp4").write_bytes(b"video")
        (tmp_path / "story_01.json").write_text(
            json.dumps(
                {
                    "video_path": str(tmp_path / "story_01.mp4"),
                    "title": "Old manifest",
                    "summary": "s",
                    "post_url": "url",
                }
            )
        )

        (video,) = satisfying_bot.load_generated_videos(str(tmp_path))

        assert video.title == "Old manifest"
        assert video.source == "auto"

    def test_manifest_with_source_keeps_it(self, tmp_path):
        (tmp_path / "story_01.mp4").write_bytes(b"video")
        (tmp_path / "story_01.json").write_text(
            json.dumps(
                {
                    "video_path": str(tmp_path / "story_01.mp4"),
                    "title": "New manifest",
                    "summary": "s",
                    "post_url": "url",
                    "source": "prepared",
                }
            )
        )

        (video,) = satisfying_bot.load_generated_videos(str(tmp_path))

        assert video.source == "prepared"


# --------------------------------------------------------------------------
# Milestone 4 — two-part packages
# --------------------------------------------------------------------------


TITLE = package_payload()["story_title"]
PART1_TITLE = f"{TITLE} - Parte 1"
PART2_TITLE = f"{TITLE} - Parte 2"


def outcome_of(queue_root, post_id: str) -> dict:
    return json.loads((queue_root / "done" / f"{post_id}.outcome.json").read_text())


class TestTwoPartGeneration:
    @pytest.mark.asyncio
    async def test_one_package_counts_as_one_story_and_makes_two_videos(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert env.discovery.calls == []
        assert env.service.prepared_urls == []
        assert env.service.generated_titles == [PART1_TITLE, PART2_TITLE]
        assert sorted(os.listdir(env.output_dir)) == [
            "story_01.json",
            "story_01.mp4",
            "story_01_p2.json",
            "story_01_p2.mp4",
        ]

    @pytest.mark.asyncio
    async def test_each_manifest_names_its_part_and_shares_the_post(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        part1, part2 = manifests(env.output_dir)
        assert part1["part"] == 1
        assert part2["part"] == 2
        assert part1["title"] == PART1_TITLE
        assert part2["title"] == PART2_TITLE
        assert part1["post_url"] == part2["post_url"] == other_post_url("aaa")
        assert part1["source"] == part2["source"] == "prepared"

    @pytest.mark.asyncio
    async def test_the_messages_announce_the_format_and_each_part(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert f'#1 Usando roteiro preparado em duas partes: "{TITLE}"' in env.messages
        assert "#1 Parte 1 gerada" in env.messages
        assert "#1 Parte 2 gerada" in env.messages
        assert not any("Gerando roteiro" in message for message in env.messages)

    @pytest.mark.asyncio
    async def test_a_single_part_package_still_makes_one_video(self, env):
        write_inbox(str(env.queue_root), "aaa", story_title="Pacote A")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        (manifest,) = manifests(env.output_dir)
        assert "part" not in manifest
        assert env.service.generated_titles == ["Pacote A"]


class TestTwoPartPublishing:
    @pytest.mark.asyncio
    async def test_both_parts_are_scheduled_in_consecutive_slots(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        first, second = env.publisher.calls
        assert first.description == PART1_TITLE
        assert second.description == PART2_TITLE
        assert second.schedule_at == satisfying_bot.next_publish_slot(
            after=first.schedule_at,
            slot_times=satisfying_bot.bot_config.publish_slots_local,
            min_lead_minutes=satisfying_bot.bot_config.publish_min_lead_minutes,
        )
        assert second.schedule_at > first.schedule_at

    @pytest.mark.asyncio
    async def test_both_parts_carry_the_packages_hashtags(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert env.llm.hashtag_calls == []
        first, second = env.publisher.calls
        assert first.hashtags == second.hashtags == ["reddit", "historia", "fyp"]

    @pytest.mark.asyncio
    async def test_hashtags_are_generated_once_and_reused(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa", hashtags=None)

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert env.llm.hashtag_calls == [PART1_TITLE]
        first, second = env.publisher.calls
        assert first.hashtags == second.hashtags

    @pytest.mark.asyncio
    async def test_publish_log_gets_one_row_per_part(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        with open(env.publish_log, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        assert [row["title"] for row in rows] == [PART1_TITLE, PART2_TITLE]
        assert {row["post_url"] for row in rows} == {other_post_url("aaa")}
        assert {row["status"] for row in rows} == {"scheduled"}

    @pytest.mark.asyncio
    async def test_done_only_after_both_parts_with_an_outcome_per_video(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert (env.queue_root / "done" / "aaa.json").exists()
        outcome = outcome_of(env.queue_root, "aaa")
        assert outcome["status"] == "scheduled"
        assert outcome["hashtags"] == ["reddit", "historia", "fyp"]
        assert [video["part"] for video in outcome["videos"]] == [1, 2]
        assert outcome["videos"][0]["video_path"].endswith("story_01.mp4")
        assert outcome["videos"][1]["video_path"].endswith("story_01_p2.mp4")
        assert outcome["videos"][1]["manifest_path"].endswith("story_01_p2.json")
        assert (
            outcome["videos"][0]["scheduled_at"] < outcome["videos"][1]["scheduled_at"]
        )


class TestTwoPartFailures:
    @pytest.mark.asyncio
    async def test_a_failed_second_video_publishes_nothing(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")
        env.service.fail_titles = {PART2_TITLE}

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert env.publisher.calls == []
        assert (env.queue_root / "failed" / "aaa.json").exists()
        assert (
            "render exploded"
            in (env.queue_root / "failed" / "aaa.error.txt").read_text()
        )

    @pytest.mark.asyncio
    async def test_a_failed_second_publish_names_the_slot_of_the_first(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")
        env.publisher.fail_descriptions = {PART2_TITLE}

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert (env.queue_root / "failed" / "aaa.json").exists()
        error = (env.queue_root / "failed" / "aaa.error.txt").read_text()
        first_slot = env.publisher.calls[0].schedule_at
        assert first_slot.strftime("%d/%m %H:%M") in error
        assert "parte 2" in error
        assert "browser exploded" in error

    @pytest.mark.asyncio
    async def test_a_failed_first_publish_fails_the_package_as_before(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")
        env.publisher.fail_descriptions = {PART1_TITLE}

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert [call.description for call in env.publisher.calls] == [PART1_TITLE]
        assert (env.queue_root / "failed" / "aaa.json").exists()
        assert (
            "browser exploded"
            in (env.queue_root / "failed" / "aaa.error.txt").read_text()
        )

    @pytest.mark.asyncio
    async def test_an_invalid_two_part_package_never_reaches_production(self, env):
        write_two_part_inbox(
            str(env.queue_root), "aaa", part1_text="Sem o convite da parte 2."
        )

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert (env.queue_root / "failed" / "aaa.json").exists()
        assert "part1_text" in (env.queue_root / "failed" / "aaa.error.txt").read_text()
        assert env.service.generated_titles == ["auto auto-url-1"]


class TestTwoPartGenerateOnly:
    @pytest.mark.asyncio
    async def test_both_videos_are_generated_and_the_package_is_done(self, env):
        videos = await satisfying_bot.run_daily_generate(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )
        assert [video.source for video in videos] == ["auto"]

    @pytest.mark.asyncio
    async def test_generate_only_marks_the_package_generated(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")

        videos = await satisfying_bot.run_daily_generate(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert [video.title for video in videos] == [PART1_TITLE, PART2_TITLE]
        assert [video.part for video in videos] == [1, 2]
        assert env.publisher.calls == []

        outcome = outcome_of(env.queue_root, "aaa")
        assert outcome["status"] == "generated"
        assert [video["part"] for video in outcome["videos"]] == [1, 2]
        assert all(video["scheduled_at"] is None for video in outcome["videos"])

    @pytest.mark.asyncio
    async def test_one_package_still_satisfies_a_target_of_one(self, env):
        write_two_part_inbox(str(env.queue_root), "aaa")

        await satisfying_bot.run_daily_generate(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert env.discovery.calls == []
        assert "✅ Geração finalizada: 1/1 vídeos prontos." in env.messages


class TestPublishFromDirectory:
    @pytest.mark.asyncio
    async def test_a_two_part_pair_is_scheduled_in_order_and_consecutively(self, env):
        os.makedirs(env.output_dir, exist_ok=True)
        for name, part, title in (
            ("story_01", 1, PART1_TITLE),
            ("story_01_p2", 2, PART2_TITLE),
        ):
            mp4 = os.path.join(env.output_dir, f"{name}.mp4")
            with open(mp4, "wb") as f:
                f.write(b"video")
            with open(os.path.join(env.output_dir, f"{name}.json"), "w") as f:
                json.dump(
                    {
                        "video_path": mp4,
                        "title": title,
                        "summary": "s",
                        "post_url": other_post_url("aaa"),
                        "source": "prepared",
                        "part": part,
                    },
                    f,
                )

        videos = satisfying_bot.load_generated_videos(env.output_dir)
        assert [video.part for video in videos] == [1, 2]

        await satisfying_bot.run_daily_publish(env.send_message, videos)

        first, second = env.publisher.calls
        assert first.description == PART1_TITLE
        assert second.description == PART2_TITLE
        assert second.schedule_at == satisfying_bot.next_publish_slot(
            after=first.schedule_at,
            slot_times=satisfying_bot.bot_config.publish_slots_local,
            min_lead_minutes=satisfying_bot.bot_config.publish_min_lead_minutes,
        )
