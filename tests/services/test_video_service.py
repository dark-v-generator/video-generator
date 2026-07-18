from types import SimpleNamespace

import pytest

from src.entities.configs.services.video import VideoConfig
from src.entities.editor.video_clip import VideoClip
from src.services import video_service
from src.services.video_service import VideoService


class FakeYouTubeProxy:
    def __init__(self):
        self.downloaded = []
        self.urls = []

    async def list_video_ids(self, url, surface="videos"):
        self.urls.append(url)
        self.surface = surface
        return ["zero", "good"]

    async def download_video(self, video_id, low_quality=False):
        self.downloaded.append(video_id)
        return video_id.encode()


class FakeVideoClip:
    def __init__(self, file_path=None, audio_clip=None, bytes=None):
        duration = 0
        if bytes and bytes.startswith(b"good"):
            duration = 45
        self.clip = SimpleNamespace(duration=duration)

    def apply_anti_fingerprint(self, config):
        return None

    def concat(self, other):
        self.clip.duration = (self.clip.duration or 0) + other.clip.duration


@pytest.mark.asyncio
async def test_youtube_compilation_skips_zero_duration_sources(monkeypatch):
    proxy = FakeYouTubeProxy()
    config = VideoConfig(youtube_pool_size=2)
    service = VideoService(proxy, config)

    monkeypatch.setattr(video_service.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(video_service.random, "shuffle", lambda items: None)

    result = await service.create_youtube_video_compilation(min_duration=30)

    assert proxy.downloaded == ["zero", "good"]
    assert proxy.urls == ["https://www.youtube.com/@FoodieBoyKR"]
    assert proxy.surface == "videos"
    assert result.clip.clip.duration == 45
    assert result.downloaded_bytes == [b"good"]


@pytest.mark.asyncio
async def test_youtube_compilation_uses_configured_surface(monkeypatch):
    proxy = FakeYouTubeProxy()
    config = VideoConfig(youtube_pool_size=2, youtube_surface="shorts")
    service = VideoService(proxy, config)

    monkeypatch.setattr(video_service.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(video_service.random, "shuffle", lambda items: None)

    await service.create_youtube_video_compilation(min_duration=30)

    assert proxy.surface == "shorts"


@pytest.mark.asyncio
async def test_youtube_compilation_randomly_selects_configured_channel(monkeypatch):
    proxy = FakeYouTubeProxy()
    config = VideoConfig(
        youtube_pool_size=2,
        youtube_channel_url="https://www.youtube.com/@fallback",
        youtube_channel_urls=[
            "https://www.youtube.com/@first",
            "https://www.youtube.com/@second",
        ],
    )
    service = VideoService(proxy, config)

    monkeypatch.setattr(video_service.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(video_service.random, "shuffle", lambda items: None)
    monkeypatch.setattr(video_service.random, "choice", lambda items: items[1])

    await service.create_youtube_video_compilation(min_duration=30)

    assert proxy.urls == ["https://www.youtube.com/@second"]


@pytest.mark.asyncio
async def test_youtube_compilation_all_strategy_merges_configured_channels(monkeypatch):
    class MultiChannelProxy:
        def __init__(self):
            self.urls = []
            self.downloaded = []

        async def list_video_ids(self, url, surface="videos"):
            self.urls.append(url)
            return {
                "https://www.youtube.com/@first": ["zero", "good1", "unused1"],
                "https://www.youtube.com/@second": ["zero2", "good2", "unused2"],
            }[url]

        async def download_video(self, video_id, low_quality=False):
            self.downloaded.append(video_id)
            return video_id.encode()

    proxy = MultiChannelProxy()
    config = VideoConfig(
        youtube_pool_size=2,
        youtube_channel_strategy="all",
        youtube_channel_urls=[
            "https://www.youtube.com/@first",
            "https://www.youtube.com/@second",
        ],
    )
    service = VideoService(proxy, config)

    monkeypatch.setattr(video_service.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(video_service.random, "shuffle", lambda items: None)

    result = await service.create_youtube_video_compilation(min_duration=80)

    assert proxy.urls == [
        "https://www.youtube.com/@first",
        "https://www.youtube.com/@second",
    ]
    assert proxy.downloaded == ["zero", "good1", "zero2", "good2"]
    assert result.clip.clip.duration == 90
    assert result.downloaded_bytes == [b"good1", b"good2"]


@pytest.mark.asyncio
async def test_youtube_compilation_all_strategy_skips_failed_channel(monkeypatch):
    class PartiallyFailingProxy:
        def __init__(self):
            self.urls = []
            self.downloaded = []

        async def list_video_ids(self, url, surface="videos"):
            self.urls.append(url)
            if url == "https://www.youtube.com/@broken":
                raise RuntimeError("channel unavailable")
            return ["good1"]

        async def download_video(self, video_id, low_quality=False):
            self.downloaded.append(video_id)
            return video_id.encode()

    proxy = PartiallyFailingProxy()
    config = VideoConfig(
        youtube_pool_size=100,
        youtube_channel_strategy="all",
        youtube_channel_urls=[
            "https://www.youtube.com/@broken",
            "https://www.youtube.com/@working",
        ],
    )
    service = VideoService(proxy, config)

    monkeypatch.setattr(video_service.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(video_service.random, "shuffle", lambda items: None)

    result = await service.create_youtube_video_compilation(min_duration=30)

    assert proxy.urls == [
        "https://www.youtube.com/@broken",
        "https://www.youtube.com/@working",
    ]
    assert proxy.downloaded == ["good1"]
    assert result.clip.clip.duration == 45


def test_adjust_duration_trims_from_beginning():
    class FakeClip:
        duration = 100

        def __init__(self):
            self.subclip_args = None

        def subclipped(self, start, end):
            self.subclip_args = (start, end)
            return self

    wrapped = VideoClip.__new__(VideoClip)
    wrapped.clip = FakeClip()

    wrapped.ajust_duration(30)

    assert wrapped.clip.subclip_args == (0, 30)
