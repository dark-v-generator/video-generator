"""The footage source is chosen by config, and a bad choice fails at load."""

import pytest
from dependency_injector import providers
from pydantic import ValidationError

from src.capabilities.footage import LocalFolderFootageSource, YouTubeFootageSource
from src.core.container import ApplicationContainer
from src.entities.config import MainConfig
from src.prompts import loader as prompts
from src.proxies.factories import TikTokStudioProxyFactory


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
