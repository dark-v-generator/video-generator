"""Tests for the daily run's modes, its dedup against the publish log and its manifests.

No network: discovery, the video service, the LLM and the publisher are all
fakes wired into the bot module.
"""

import json
import os
from types import SimpleNamespace

import pytest

from bots import satisfying_bot
from src.entities.reddit_post import RedditPost
from src.entities.story_candidate import EvaluatedStory
from src.services.reddit_video_service import PreparedStory
from tests.fakes.publisher import FakePublisher

# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


class FakeService:
    def __init__(self):
        self.prepared_urls = []
        self.generated_titles = []

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
        return SimpleNamespace(video=b"video", localized_title=prepared.story_title)


class FakeLLM:
    async def generate_hashtags(self, *, title, summary, target_language):
        return ["fyp"]


class FakeContainer:
    def __init__(self, service, llm):
        self._service = service
        self._llm = llm

    def wire(self, modules):
        return None

    def reddit_video_service(self):
        return self._service

    def llm_proxy(self):
        return self._llm


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
    service = FakeService()
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
    monkeypatch.setattr(satisfying_bot, "container", FakeContainer(service, FakeLLM()))
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
        ),
    )

    return SimpleNamespace(
        service=service,
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
# run_daily_auto_publish
# --------------------------------------------------------------------------


class TestAutoPublish:
    @pytest.mark.asyncio
    async def test_discovery_skips_posts_already_scheduled(self, env):
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
        assert [call.description for call in env.publisher.calls] == [
            "auto auto-url-1",
            "auto auto-url-2",
        ]

    @pytest.mark.asyncio
    async def test_manifests_say_the_story_came_from_discovery(self, env):
        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        (manifest,) = manifests(env.output_dir)
        assert manifest["source"] == "auto"
        assert "part" not in manifest

    @pytest.mark.asyncio
    async def test_nothing_found_says_so(self, env):
        env.discovery.results = []

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=2, output_dir=env.output_dir
        )

        assert env.messages == [
            "🔄 Busca diária iniciada...",
            "Nenhuma história boa encontrada hoje.",
        ]

    @pytest.mark.asyncio
    async def test_discovery_failure_is_reported(self, env):
        env.discovery.error = RuntimeError("reddit down")

        await satisfying_bot.run_daily_auto_publish(
            env.send_message, publish_count=2, output_dir=env.output_dir
        )

        assert env.messages == [
            "🔄 Busca diária iniciada...",
            "Erro ao buscar histórias: reddit down",
        ]


# --------------------------------------------------------------------------
# run_daily_generate
# --------------------------------------------------------------------------


class TestGenerateOnly:
    @pytest.mark.asyncio
    async def test_generates_without_publishing(self, env):
        videos = await satisfying_bot.run_daily_generate(
            env.send_message, publish_count=1, output_dir=env.output_dir
        )

        assert [video.source for video in videos] == ["auto"]
        assert env.discovery.calls == [set()]
        assert env.publisher.calls == []
        assert "✅ Geração finalizada: 1/1 vídeos prontos." in env.messages


# --------------------------------------------------------------------------
# Dedup against the publish log
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


def write_manifest(directory, name: str, **fields) -> None:
    mp4 = os.path.join(directory, f"{name}.mp4")
    with open(mp4, "wb") as f:
        f.write(b"video")
    with open(os.path.join(directory, f"{name}.json"), "w") as f:
        json.dump({"video_path": mp4, "summary": "s", **fields}, f)


class TestLoadGeneratedVideos:
    def test_manifest_without_source_still_loads(self, tmp_path):
        write_manifest(tmp_path, "story_01", title="Old manifest", post_url="url")

        (video,) = satisfying_bot.load_generated_videos(str(tmp_path))

        assert video.title == "Old manifest"
        assert video.source == "auto"

    def test_manifest_with_source_keeps_it(self, tmp_path):
        write_manifest(
            tmp_path, "story_01", title="New manifest", post_url="url", source="manual"
        )

        (video,) = satisfying_bot.load_generated_videos(str(tmp_path))

        assert video.source == "manual"

    def test_manifest_with_a_part_number_still_loads(self, tmp_path):
        # Manifests from the removed flow that split a story across videos.
        write_manifest(
            tmp_path, "story_01", title="Half", post_url="url", source="auto", part=2
        )

        (video,) = satisfying_bot.load_generated_videos(str(tmp_path))

        assert video.title == "Half"

    def test_manifest_whose_video_is_gone_is_skipped(self, tmp_path):
        write_manifest(tmp_path, "story_01", title="Gone", post_url="url")
        os.remove(tmp_path / "story_01.mp4")

        assert satisfying_bot.load_generated_videos(str(tmp_path)) == []


# --------------------------------------------------------------------------
# run_daily_publish
# --------------------------------------------------------------------------


class TestPublishFromDirectory:
    @pytest.mark.asyncio
    async def test_videos_are_scheduled_in_order_and_consecutively(self, env):
        os.makedirs(env.output_dir, exist_ok=True)
        write_manifest(env.output_dir, "story_01", title="First", post_url="url-1")
        write_manifest(env.output_dir, "story_02", title="Second", post_url="url-2")

        videos = satisfying_bot.load_generated_videos(env.output_dir)
        await satisfying_bot.run_daily_publish(env.send_message, videos)

        first, second = env.publisher.calls
        assert first.description == "First"
        assert second.description == "Second"
        assert second.schedule_at == satisfying_bot.next_publish_slot(
            after=first.schedule_at,
            slot_times=satisfying_bot.bot_config.publish_slots_local,
            min_lead_minutes=satisfying_bot.bot_config.publish_min_lead_minutes,
        )

    @pytest.mark.asyncio
    async def test_a_failed_video_is_logged_and_the_next_one_still_goes(self, env):
        os.makedirs(env.output_dir, exist_ok=True)
        write_manifest(env.output_dir, "story_01", title="First", post_url="url-1")
        write_manifest(env.output_dir, "story_02", title="Second", post_url="url-2")
        env.publisher._fail_on = {1}

        videos = satisfying_bot.load_generated_videos(env.output_dir)
        await satisfying_bot.run_daily_publish(env.send_message, videos)

        assert [call.description for call in env.publisher.calls] == [
            "First",
            "Second",
        ]
        rows = env.publish_log.read_text().splitlines()
        assert [row.split(",")[1] for row in rows[1:]] == ["failed", "scheduled"]
        assert env.messages[-1] == "🏁 Agendamento concluído."
