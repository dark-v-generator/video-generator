"""Fake footage and composer: record what was asked for and write fixed bytes."""

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import List

from src.capabilities.footage import Footage

FAKE_VIDEO_BYTES = b"fake-mp4"


class _FakeRenderedClip:
    def __init__(self, payload: bytes):
        self._payload = payload

    def write_videofile(self, path: str, fps=None, ffmpeg_params=None, **_) -> None:
        with open(path, "wb") as f:
            f.write(self._payload)


@dataclass
class Composition:
    audio_duration: float
    cta_start: float
    captions: List[str]
    low_quality: bool


@dataclass
class FakeFootageSource:
    """A ``FootageSource`` that hands back an empty clip: no download, no decode."""

    compilations: List[float] = field(default_factory=list)

    async def compile(self, *, min_duration: float, low_quality: bool = False):
        self.compilations.append(min_duration)
        return Footage(clip=SimpleNamespace(), sources=["fake"])


@dataclass
class FakeComposer:
    """Stands in for ``VideoComposer``: no moviepy render."""

    payload: bytes = FAKE_VIDEO_BYTES
    compositions: List[Composition] = field(default_factory=list)

    def compose(
        self,
        audio,
        background_video,
        low_quality: bool = False,
        cover=None,
        captions=None,
        cta_start: float = 0,
    ):
        self.compositions.append(
            Composition(
                audio_duration=audio.clip.duration,
                cta_start=cta_start,
                captions=(
                    [s.text for s in captions.captions.segments] if captions else []
                ),
                low_quality=low_quality,
            )
        )
        return SimpleNamespace(clip=_FakeRenderedClip(self.payload))
