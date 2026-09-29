"""The footage source is chosen by config, and a bad choice fails at load."""

import pytest
from dependency_injector import providers
from pydantic import ValidationError

from src.capabilities.footage import LocalFolderFootageSource, YouTubeFootageSource
from src.capabilities.performance import StudioPerformanceSource
from src.core.container import ApplicationContainer
from src.entities.config import MainConfig
from src.entities.configs.flows import CollectionConfig
from src.prompts import loader as prompts
from src.proxies.factories import TikTokStudioProxyFactory
from src.proxies.tiktok_studio_proxy import PatchrightTikTokStudioProxy
from src.storage import SqliteHistoryStore


def _container(tmp_path, video_config: str) -> ApplicationContainer:
    path = tmp_path / "config.yaml"
    path.write_text(f"services:\n  video_config:\n{video_config}", encoding="utf-8")
    container = ApplicationContainer()
    container.main_config.override(
        providers.Singleton(MainConfig.from_yaml, file_path=str(path))
    )
    return container


def test_youtube_is_the_default(tmp_path):
    container = _container(tmp_path, "    fps: 30\n")

    assert isinstance(container.footage_source(), YouTubeFootageSource)


def test_local_uses_the_folder_and_never_builds_the_youtube_proxy(tmp_path):
    def youtube_must_not_be_built():
        raise AssertionError("the YouTube proxy was constructed")

    container = _container(
        tmp_path,
        f"    footage_source: local\n    local_footage_dir: {tmp_path}\n",
    )
    container.youtube_proxy.override(providers.Callable(youtube_must_not_be_built))

    assert isinstance(container.footage_source(), LocalFolderFootageSource)
    assert isinstance(container.renderer()._footage, LocalFolderFootageSource)


def test_local_without_a_directory_fails_naming_the_key(tmp_path):
    container = _container(tmp_path, "    footage_source: local\n")

    with pytest.raises(ValidationError, match="local_footage_dir"):
        container.main_config()


def test_the_history_path_is_read_on_every_call(tmp_path, monkeypatch):
    container = ApplicationContainer()

    monkeypatch.setenv("HISTORY_DB_PATH", str(tmp_path / "a" / "history.sqlite"))
    container.history_store()
    monkeypatch.setenv("HISTORY_DB_PATH", str(tmp_path / "b" / "history.sqlite"))
    container.history_store()

    assert (tmp_path / "a" / "history.sqlite").exists()
    assert (tmp_path / "b" / "history.sqlite").exists()


def test_the_exploration_plan_is_read_again_at_every_run(tmp_path, monkeypatch):
    container = ApplicationContainer()
    for name, share in (("a", 0.25), ("b", 0.4)):
        (tmp_path / name).mkdir()
        (tmp_path / name / "exploration.yaml").write_text(
            f"cycle: 2\nshare: {share}\nshare_since: 2026-10-01\n", encoding="utf-8"
        )
    source = container.exploration_source

    monkeypatch.setenv("TUNING_DIR", str(tmp_path / "a"))
    assert source().plan().share == 0.25
    monkeypatch.setenv("TUNING_DIR", str(tmp_path / "b"))
    assert source().plan().share == 0.4
    # A new source per run, so a plan deployed while the bot is up counts.
    assert source() is not source()


@pytest.mark.parametrize(
    "config_file, writer, grader, rate",
    [
        ("config.dev.yaml", "mock", "mock", 1.2),
        (
            "config.prod.yaml",
            "openrouter/moonshotai/kimi-k2.6",
            "openrouter/deepseek/deepseek-v4-flash",
            1.5,
        ),
    ],
)
def test_the_recipe_comes_from_the_config_and_the_prompt_files(
    config_file, writer, grader, rate
):
    container = ApplicationContainer()
    container.main_config.override(
        providers.Singleton(MainConfig.from_yaml, file_path=config_file)
    )

    recipe = container.production_recipe()

    assert recipe.story_prompt_version == prompts.fingerprint("story.jinja2")
    assert recipe.grading_prompt_version == prompts.fingerprint("evaluate_story.jinja2")
    assert recipe.hashtags_prompt_version == prompts.fingerprint(
        "generate_hashtags.jinja2"
    )
    assert recipe.exploration_prompt_version == prompts.fingerprint(
        "evaluate_exploration.jinja2"
    )
    assert (recipe.writer_model, recipe.grader_model) == (writer, grader)
    assert recipe.rendering_strategy == "narration-over-footage"
    assert (recipe.speech_provider, recipe.speech_rate) == ("edge-tts", rate)
    # The run fills these per story.
    assert (recipe.narrator_gender, recipe.voice_id) == ("", "")


def test_without_a_story_model_the_writer_is_the_main_model(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "proxies:\n"
        "  llm_config:\n"
        "    type: prompt\n"
        "    provider_config:\n"
        "      provider: openai\n"
        "      model: gpt-x\n"
        "  speech_config:\n"
        "    type: elevenlabs\n",
        encoding="utf-8",
    )
    container = ApplicationContainer()
    container.main_config.override(
        providers.Singleton(MainConfig.from_yaml, file_path=str(path))
    )

    recipe = container.production_recipe()

    assert recipe.writer_model == recipe.grader_model == "openai/gpt-x"
    assert (recipe.speech_provider, recipe.speech_rate) == ("elevenlabs", None)


def _proxies(tmp_path, proxies: str) -> MainConfig:
    path = tmp_path / "config.yaml"
    path.write_text(f"proxies:\n{proxies}", encoding="utf-8")
    return MainConfig.from_yaml(str(path))


def test_the_studio_reads_the_publishers_profile_by_default(tmp_path):
    config = _proxies(
        tmp_path,
        "  tiktok_publisher_config:\n"
        f"    cookies_path: {tmp_path}/session/tiktok_cookies.json\n",
    ).proxies

    profile = TikTokStudioProxyFactory.profile(
        config.tiktok_studio_config, config.tiktok_publisher_config
    )

    assert profile == tmp_path.resolve() / "session" / "tiktok_cookies_userdata"


def test_a_studio_profile_in_the_config_wins(tmp_path):
    config = _proxies(
        tmp_path,
        f"  tiktok_studio_config:\n    user_data_dir: {tmp_path}/studio\n",
    ).proxies

    profile = TikTokStudioProxyFactory.profile(
        config.tiktok_studio_config, config.tiktok_publisher_config
    )

    assert profile == tmp_path.resolve() / "studio"


def test_the_studio_reader_is_built_on_the_publishers_profile(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "proxies:\n  tiktok_publisher_config:\n"
        f"    cookies_path: {tmp_path}/tiktok_cookies.json\n"
        "  tiktok_studio_config:\n    page_timeout_seconds: 5\n",
        encoding="utf-8",
    )
    container = ApplicationContainer()
    container.main_config.override(
        providers.Singleton(MainConfig.from_yaml, file_path=str(path))
    )

    proxy = container.tiktok_studio_proxy()

    assert isinstance(proxy, PatchrightTikTokStudioProxy)
    assert proxy._user_data_dir == tmp_path.resolve() / "tiktok_cookies_userdata"
    assert proxy._timeout == 5


def test_the_collection_reads_the_studio_with_the_configured_window(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("HISTORY_DB_PATH", str(tmp_path / "history.sqlite"))
    path = tmp_path / "config.yaml"
    path.write_text(
        "proxies:\n  llm_config:\n    type: mock\n"
        "  tiktok_publisher_config:\n"
        f"    cookies_path: {tmp_path}/tiktok_cookies.json\n"
        "  tiktok_studio_config:\n    lookback_days: 14\n    max_gap_hours: 6\n",
        encoding="utf-8",
    )
    container = ApplicationContainer()
    container.main_config.override(
        providers.Singleton(MainConfig.from_yaml, file_path=str(path))
    )

    async def progress(text):
        pass

    collection = container.performance_collection(progress=progress)

    assert collection.config == CollectionConfig(lookback_days=14, max_gap_hours=6)
    assert isinstance(collection.source, StudioPerformanceSource)
    assert isinstance(collection.source._proxy, PatchrightTikTokStudioProxy)
    assert isinstance(collection.history, SqliteHistoryStore)
    assert (tmp_path / "history.sqlite").exists()
