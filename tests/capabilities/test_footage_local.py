"""Local footage: the .mp4 files of one folder, concatenated, no network."""

from types import SimpleNamespace

import pytest

from src.capabilities.footage import (
    FootageShortfallError,
    LocalFolderFootageSource,
    local_folder,
)
from src.entities.configs.services.video import VideoConfig

DURATIONS = {"a.mp4": 40.0, "b.mp4": 30.0, "c.MP4": 20.0}


class FakeVideoClip:
    """Reads the duration from DURATIONS by file name instead of decoding."""

    opened: list[str] = []

    def __init__(self, file_path=None, audio_clip=None, bytes=None):
        duration = 0.0
        if file_path is not None:
            name = file_path.rsplit("/", 1)[-1]
            FakeVideoClip.opened.append(name)
            duration = DURATIONS.get(name, 0.0)
        self.clip = SimpleNamespace(duration=duration)
        self.fingerprinted = False

    def apply_anti_fingerprint(self, config):
        self.fingerprinted = True

    def concat(self, other):
        assert other.fingerprinted, "every clip is fingerprinted before concat"
        self.clip.duration = (self.clip.duration or 0) + other.clip.duration


@pytest.fixture
def folder(tmp_path, monkeypatch):
    for name in [*DURATIONS, "notes.txt"]:
        (tmp_path / name).write_bytes(b"")
    (tmp_path / "nested.mp4").mkdir()
    FakeVideoClip.opened = []
    monkeypatch.setattr(local_folder.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(local_folder.random, "shuffle", lambda items: None)
    return tmp_path


@pytest.mark.asyncio
async def test_concatenates_clips_until_the_duration_is_covered(folder):
    source = LocalFolderFootageSource(str(folder), VideoConfig())

    footage = await source.compile(min_duration=65)

    assert footage.sources == ["a.mp4", "b.mp4"]
    assert footage.clip.clip.duration == 70
    assert FakeVideoClip.opened == ["a.mp4", "b.mp4"], "stops once covered"


@pytest.mark.asyncio
async def test_only_mp4_files_are_used(folder):
    source = LocalFolderFootageSource(str(folder), VideoConfig())

    footage = await source.compile(min_duration=90)

    assert footage.sources == ["a.mp4", "b.mp4", "c.MP4"]


@pytest.mark.asyncio
async def test_order_is_shuffled(folder, monkeypatch):
    monkeypatch.setattr(local_folder.random, "shuffle", lambda items: items.reverse())
    source = LocalFolderFootageSource(str(folder), VideoConfig())

    footage = await source.compile(min_duration=10)

    assert footage.sources == ["c.MP4"]


@pytest.mark.asyncio
async def test_shortfall_names_the_deficit(folder):
    source = LocalFolderFootageSource(str(folder), VideoConfig())

    with pytest.raises(FootageShortfallError) as excinfo:
        await source.compile(min_duration=120)

    assert (excinfo.value.needed, excinfo.value.got) == (120, 90)
    assert "short by 30.0s" in str(excinfo.value)
    assert "3 .mp4 file(s)" in str(excinfo.value)


@pytest.mark.asyncio
async def test_empty_folder_is_a_shortfall(tmp_path):
    source = LocalFolderFootageSource(str(tmp_path), VideoConfig())

    with pytest.raises(FootageShortfallError) as excinfo:
        await source.compile(min_duration=30)

    assert excinfo.value.got == 0


@pytest.mark.asyncio
async def test_zero_duration_clip_fails_naming_the_file(folder):
    (folder / "broken.mp4").write_bytes(b"")
    source = LocalFolderFootageSource(str(folder), VideoConfig())

    with pytest.raises(ValueError, match="broken.mp4"):
        await source.compile(min_duration=500)


def test_missing_directory_fails_at_construction(tmp_path):
    with pytest.raises(ValueError, match="local_footage_dir"):
        LocalFolderFootageSource(str(tmp_path / "nope"), VideoConfig())
