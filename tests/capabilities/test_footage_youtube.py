"""YouTube footage: channel strategies, pool, skips and the 429 fallback."""

from types import SimpleNamespace

import pytest

from src.capabilities.footage import FootageShortfallError, youtube
from src.capabilities.footage.youtube import YouTubeFootageSource
from src.entities.configs.services.video import VideoConfig
from src.proxies.interfaces import IYouTubeProxy
from src.proxies.pytube_proxy import YouTubeRateLimitError


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
    source = YouTubeFootageSource(proxy, config)

    monkeypatch.setattr(youtube.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(youtube.random, "shuffle", lambda items: None)

    result = await source.compile(min_duration=30)

    assert proxy.downloaded == ["zero", "good"]
    assert proxy.urls == ["https://www.youtube.com/@FoodieBoyKR"]
    assert proxy.surface == "videos"
    assert result.clip.clip.duration == 45
    assert result.sources == ["good"]


@pytest.mark.asyncio
async def test_youtube_compilation_uses_configured_surface(monkeypatch):
    proxy = FakeYouTubeProxy()
    config = VideoConfig(youtube_pool_size=2, youtube_surface="shorts")
    source = YouTubeFootageSource(proxy, config)

    monkeypatch.setattr(youtube.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(youtube.random, "shuffle", lambda items: None)

    await source.compile(min_duration=30)

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
    source = YouTubeFootageSource(proxy, config)

    monkeypatch.setattr(youtube.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(youtube.random, "shuffle", lambda items: None)
    monkeypatch.setattr(youtube.random, "choice", lambda items: items[1])

    await source.compile(min_duration=30)

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
    source = YouTubeFootageSource(proxy, config)

    monkeypatch.setattr(youtube.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(youtube.random, "shuffle", lambda items: None)

    result = await source.compile(min_duration=80)

    assert proxy.urls == [
        "https://www.youtube.com/@first",
        "https://www.youtube.com/@second",
    ]
    assert proxy.downloaded == ["zero", "good1", "zero2", "good2"]
    assert result.clip.clip.duration == 90
    assert result.sources == ["good1", "good2"]


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
    source = YouTubeFootageSource(proxy, config)

    monkeypatch.setattr(youtube.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(youtube.random, "shuffle", lambda items: None)

    result = await source.compile(min_duration=30)

    assert proxy.urls == [
        "https://www.youtube.com/@broken",
        "https://www.youtube.com/@working",
    ]
    assert proxy.downloaded == ["good1"]
    assert result.clip.clip.duration == 45


@pytest.mark.asyncio
async def test_exhausted_pool_raises_shortfall_with_the_deficit(monkeypatch):
    proxy = FakeYouTubeProxy()
    source = YouTubeFootageSource(proxy, VideoConfig(youtube_pool_size=2))

    monkeypatch.setattr(youtube.video_clip, "VideoClip", FakeVideoClip)
    monkeypatch.setattr(youtube.random, "shuffle", lambda items: None)

    with pytest.raises(FootageShortfallError) as excinfo:
        await source.compile(min_duration=100)

    assert (excinfo.value.needed, excinfo.value.got) == (100, 45)
    assert "short by 55.0s" in str(excinfo.value)


# --- rate limit ---------------------------------------------------------
# A 429 must stop the compilation, not send it through the whole pool.
#
# The YouTube compilation used to swallow every download failure and
# continue. With ~150 ids across the configured channels that meant one throttled
# run fired hundreds of requests at the endpoint already refusing it — which kept
# the block alive well past when it would otherwise have expired, and surfaced to
# the user only as "compilation completed with 0.0s duration".


class _Proxy(IYouTubeProxy):
    """Lists a big pool; every download is throttled, and nothing is local."""

    def __init__(self, pool=150):
        self.pool = pool
        self.download_attempts = 0

    async def list_video_ids(self, url, surface="videos"):
        return [f"vid{i:08d}00" for i in range(self.pool)]

    async def download_video(self, video_id, low_quality=False):
        self.download_attempts += 1
        raise YouTubeRateLimitError("HTTP 429")


def _source(proxy):
    config = VideoConfig(
        watermark_path=None,
        call_to_action_path=None,
        youtube_channel_urls=["https://www.youtube.com/@a"],
        youtube_channel_strategy="all",
    )
    return YouTubeFootageSource(proxy, config)


@pytest.mark.asyncio
async def test_rate_limit_aborts_after_a_single_download_attempt():
    proxy = _Proxy()
    source = _source(proxy)

    with pytest.raises(YouTubeRateLimitError):
        await source.compile(min_duration=60)

    assert proxy.download_attempts == 1, (
        f"walked {proxy.download_attempts} videos while throttled; "
        "should stop at the first 429"
    )


@pytest.mark.asyncio
async def test_rate_limit_surfaces_instead_of_the_0s_duration_message():
    # The old path reported an empty compilation, which hid the real cause.
    proxy = _Proxy()
    source = _source(proxy)

    with pytest.raises(YouTubeRateLimitError) as excinfo:
        await source.compile(min_duration=60)

    assert "0.0s" not in str(excinfo.value)


@pytest.mark.asyncio
async def test_ordinary_failures_still_skip_to_the_next_video():
    class Flaky(_Proxy):
        async def download_video(self, video_id, low_quality=False):
            self.download_attempts += 1
            raise RuntimeError("unavailable")

    proxy = Flaky(pool=5)
    source = _source(proxy)

    with pytest.raises(Exception) as excinfo:
        await source.compile(min_duration=60)

    assert not isinstance(excinfo.value, YouTubeRateLimitError)
    assert proxy.download_attempts == 5, "should still try every candidate"


class _ProxyWithLocalClips(_Proxy):
    """Throttled by YouTube, but holding usable clips on disk.

    Mirrors the real shape of the problem: the network refuses us while the
    background cache already holds more than the compilation needs.
    """

    def __init__(self, local_ids, pool=150, seconds_each=40.0):
        super().__init__(pool=pool)
        self._local = list(local_ids)
        self.seconds_each = seconds_each
        self.served_locally = []

    def locally_available(self, video_ids, low_quality=False):
        return [v for v in video_ids if v in self._local]

    async def download_video(self, video_id, low_quality=False):
        self.download_attempts += 1
        if video_id in self._local:
            self.served_locally.append(video_id)
            return b"cached-clip-bytes"
        raise YouTubeRateLimitError("HTTP 429")


@pytest.fixture
def local_clips_play(monkeypatch):
    """Make cached bytes decode to a fixed-length clip."""

    class _Clip:
        def __init__(self, bytes=None, **kwargs):
            self.clip = SimpleNamespace(duration=40.0)

        def apply_anti_fingerprint(self, *_args, **_kwargs):
            pass

        def concat(self, _other):
            pass

    monkeypatch.setattr(youtube.video_clip, "VideoClip", _Clip)


@pytest.mark.asyncio
async def test_throttled_run_finishes_from_local_clips(local_clips_play):
    # The whole point of the cache: a throttled run still produces a video.
    pool = [f"vid{i:08d}00" for i in range(150)][:50]  # what the pool cap admits
    proxy = _ProxyWithLocalClips(local_ids=pool[-6:])
    source = _source(proxy)

    result = await source.compile(min_duration=120)

    assert len(result.sources) == 3, "40s clips should cover 120s with 3"
    assert proxy.served_locally, "should have fallen back to the cached clips"


@pytest.mark.asyncio
async def test_fallback_makes_no_further_network_attempts(local_clips_play):
    pool = [f"vid{i:08d}00" for i in range(150)][:50]  # what the pool cap admits
    proxy = _ProxyWithLocalClips(local_ids=pool[-6:])
    source = _source(proxy)

    await source.compile(min_duration=120)

    # One throttled attempt, then only local reads — never a walk of the pool.
    network_attempts = proxy.download_attempts - len(proxy.served_locally)
    assert network_attempts == 1, (
        f"made {network_attempts} network attempts while throttled; "
        "the fallback must not go back to YouTube"
    )


@pytest.mark.asyncio
async def test_throttle_still_raises_when_local_clips_cannot_cover_it(local_clips_play):
    pool = [f"vid{i:08d}00" for i in range(150)][:50]
    proxy = _ProxyWithLocalClips(local_ids=pool[-1:])  # 40s only
    source = _source(proxy)

    with pytest.raises(YouTubeRateLimitError):
        await source.compile(min_duration=300)


@pytest.mark.asyncio
async def test_throttle_raises_the_original_error_not_a_bare_reraise(local_clips_play):
    proxy = _ProxyWithLocalClips(local_ids=[])
    source = _source(proxy)

    with pytest.raises(YouTubeRateLimitError) as excinfo:
        await source.compile(min_duration=60)

    assert "HTTP 429" in str(excinfo.value)
