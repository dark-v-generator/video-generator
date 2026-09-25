"""Fake video service: records what would be composed and writes fixed bytes."""

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import List, Optional

from src.entities.configs.services.video import VideoConfig

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
class FakeVideoService:
    """Stands in for ``VideoService``: no footage download, no moviepy render."""

    _video_config: VideoConfig = field(default_factory=VideoConfig)
    payload: bytes = FAKE_VIDEO_BYTES
    compilations: List[float] = field(default_factory=list)
    compositions: List[Composition] = field(default_factory=list)

    async def create_youtube_video_compilation(
        self, min_duration: float, low_quality: bool = False
    ):
        self.compilations.append(min_duration)
        return SimpleNamespace(clip=SimpleNamespace(), downloaded_bytes=[])

    def generate_video(
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
