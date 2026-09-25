"""The footage source is chosen by config, and a bad choice fails at load."""

import pytest
from dependency_injector import providers
from pydantic import ValidationError

from src.capabilities.footage import LocalFolderFootageSource, YouTubeFootageSource
from src.core.container import ApplicationContainer
from src.entities.config import MainConfig


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
