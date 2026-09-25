import logging
import random
from typing import List

from ...entities.configs.services.video import VideoConfig
from ...entities.editor import video_clip
from ...proxies.interfaces import IYouTubeProxy
from ...proxies.pytube_proxy import YouTubeRateLimitError
from .contract import Footage, FootageShortfallError

logger = logging.getLogger(__name__)


class YouTubeFootageSource:
    """Background footage from the configured YouTube channels, via the cache."""

    def __init__(self, youtube: IYouTubeProxy, video_config: VideoConfig):
        self._youtube_proxy = youtube
        self._video_config = video_config

    async def compile(
        self, *, min_duration: float, low_quality: bool = False
    ) -> Footage:
        video_ids = await self._list_youtube_compilation_video_ids()
        random.shuffle(video_ids)

        video = video_clip.VideoClip()
        sources: List[str] = []
        total_duration = 0

        for index, video_id in enumerate(video_ids):
            try:
                video_bytes = await self._youtube_proxy.download_video(
                    video_id, low_quality
                )
                new_video = video_clip.VideoClip(bytes=video_bytes)
                duration = float(new_video.clip.duration or 0)
            except YouTubeRateLimitError as throttled:
                # Every remaining video would hit the same per-IP throttle, and
                # the pool is ~150 ids across the configured channels — walking
                # it here is what kept the block alive between runs. So stop
                # asking the network, but finish the compilation from whatever
                # is already on disk instead of throwing the run away: the
                # backgrounds we hold are as good as the ones we cannot reach.
                logger.error(
                    "YouTube is rate-limiting this IP after %d clip(s); "
                    "finishing from locally available backgrounds only",
                    len(sources),
                )
                return await self._finish_without_network(
                    video=video,
                    sources=sources,
                    total_duration=total_duration,
                    remaining_ids=video_ids[index + 1 :],
                    min_duration=min_duration,
                    low_quality=low_quality,
                    throttle_error=throttled,
                )
            except Exception:
                logger.exception("Skipping unusable YouTube background %s", video_id)
                continue

            if duration <= 0:
                logger.warning(
                    "Skipping zero-duration YouTube background %s",
                    video_id,
                )
                continue

            sources.append(video_id)
            new_video.apply_anti_fingerprint(self._video_config.anti_fingerprint)
            video.concat(new_video)
            total_duration += duration

            if total_duration >= min_duration:
                return Footage(clip=video, sources=sources)

        if total_duration < min_duration:
            raise FootageShortfallError(
                min_duration, total_duration, "all available YouTube videos used"
            )
        return Footage(clip=video, sources=sources)

    async def _finish_without_network(
        self,
        video: video_clip.VideoClip,
        sources: List[str],
        total_duration: float,
        remaining_ids: List[str],
        min_duration: float,
        low_quality: bool,
        throttle_error: YouTubeRateLimitError,
    ) -> Footage:
        """Top the compilation up from backgrounds already held locally.

        Reached only once YouTube has refused us, so this must not make a
        single further request. Anything the proxy reports as locally
        available is fetched; anything that turns out not to be is skipped
        rather than allowed to fail the run, because by this point a finished
        video built from older backgrounds beats no video at all.
        """
        local_ids = self._youtube_proxy.locally_available(remaining_ids, low_quality)
        if not local_ids:
            logger.error(
                "No locally available backgrounds to fall back on; "
                "compilation has %.1fs of the %.1fs needed",
                total_duration,
                min_duration,
            )
            raise throttle_error

        logger.info(
            "Falling back to %d locally available background(s)", len(local_ids)
        )

        for video_id in local_ids:
            try:
                video_bytes = await self._youtube_proxy.download_video(
                    video_id, low_quality
                )
                new_video = video_clip.VideoClip(bytes=video_bytes)
                duration = float(new_video.clip.duration or 0)
            except YouTubeRateLimitError:
                # The entry went away between the check and the read, so this
                # one fell through to the network after all. Stop: every other
                # local clip is still worth trying, but this id is not.
                logger.warning(
                    "Locally available background %s needed the network after "
                    "all; skipping it",
                    video_id,
                )
                continue
            except Exception:
                logger.exception("Skipping unusable YouTube background %s", video_id)
                continue

            if duration <= 0:
                logger.warning("Skipping zero-duration YouTube background %s", video_id)
                continue

            sources.append(video_id)
            new_video.apply_anti_fingerprint(self._video_config.anti_fingerprint)
            video.concat(new_video)
            total_duration += duration

            if total_duration >= min_duration:
                logger.info(
                    "Compilation completed from local backgrounds despite the "
                    "throttle (%.1fs)",
                    total_duration,
                )
                return Footage(clip=video, sources=sources)

        logger.error(
            "Local backgrounds were not enough: %.1fs of the %.1fs needed",
            total_duration,
            min_duration,
        )
        raise throttle_error

    async def _list_youtube_compilation_video_ids(self) -> List[str]:
        channel_urls = self._youtube_channel_urls()
        strategy = self._video_config.youtube_channel_strategy

        if strategy == "random":
            channel_url = random.choice(channel_urls)
            logger.info("Creating YouTube compilation from channel %s", channel_url)
            return await self._list_channel_video_ids(channel_url)

        if strategy == "all":
            logger.info(
                "Creating YouTube compilation from %d configured channels",
                len(channel_urls),
            )
            video_ids: List[str] = []
            seen: set[str] = set()
            failures: list[str] = []

            for channel_url in channel_urls:
                try:
                    channel_video_ids = await self._list_channel_video_ids(channel_url)
                except Exception as exc:
                    logger.exception(
                        "Skipping YouTube channel %s after list failure", channel_url
                    )
                    failures.append(f"{channel_url}: {exc}")
                    continue

                for video_id in channel_video_ids:
                    if video_id not in seen:
                        seen.add(video_id)
                        video_ids.append(video_id)

            if not video_ids and failures:
                raise RuntimeError(
                    "Failed to list usable YouTube backgrounds from any configured "
                    f"channel. First failure: {failures[0]}"
                )
            return video_ids

        raise ValueError(f"Unknown YouTube channel strategy: {strategy}")

    async def _list_channel_video_ids(self, channel_url: str) -> List[str]:
        video_ids = await self._youtube_proxy.list_video_ids(
            channel_url,
            surface=self._video_config.youtube_surface,
        )

        pool = self._video_config.youtube_pool_size
        if pool > 0:
            return video_ids[:pool]
        return video_ids

    def _youtube_channel_urls(self) -> List[str]:
        channel_urls = [
            url.strip()
            for url in self._video_config.youtube_channel_urls
            if url and url.strip()
        ]
        if not channel_urls and self._video_config.youtube_channel_url:
            channel_urls = [self._video_config.youtube_channel_url.strip()]
        if not channel_urls:
            raise ValueError("At least one YouTube channel URL must be configured")
        return channel_urls
