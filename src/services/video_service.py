import logging
import random
from dataclasses import dataclass
from typing import Optional, List


from ..proxies.interfaces import IYouTubeProxy
from ..proxies.pytube_proxy import YouTubeRateLimitError
from ..entities.configs.services.video import VideoConfig

from ..entities.editor import image_clip, audio_clip, video_clip, captions_clip

logger = logging.getLogger(__name__)


@dataclass
class YouTubeCompilationResult:
    clip: video_clip.VideoClip
    downloaded_bytes: List[bytes]


class VideoService:
    """Video generation service implementation"""

    def __init__(
        self,
        youtube_proxy: IYouTubeProxy,
        video_config: VideoConfig,
    ):
        self._youtube_proxy = youtube_proxy
        self._video_config = video_config
        self._watermark_bytes = None
        if self._video_config.watermark_path:
            with open(self._video_config.watermark_path, "rb") as f:
                self._watermark_bytes = f.read()

        self._call_to_action_bytes = None
        if self._video_config.call_to_action_path:
            with open(self._video_config.call_to_action_path, "rb") as f:
                self._call_to_action_bytes = f.read()

    async def create_youtube_video_compilation(
        self, min_duration: int, low_quality: bool = False
    ) -> YouTubeCompilationResult:
        """Create video compilation from YouTube content"""

        video_ids = await self._list_youtube_compilation_video_ids()
        random.shuffle(video_ids)

        video = video_clip.VideoClip()
        downloaded_bytes: List[bytes] = []
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
                    len(downloaded_bytes),
                )
                return await self._finish_without_network(
                    video=video,
                    downloaded_bytes=downloaded_bytes,
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

            downloaded_bytes.append(video_bytes)
            new_video.apply_anti_fingerprint(self._video_config.anti_fingerprint)
            video.concat(new_video)
            total_duration += duration

            if total_duration >= min_duration:
                return YouTubeCompilationResult(
                    clip=video, downloaded_bytes=downloaded_bytes
                )
        if total_duration < min_duration:
            raise Exception(
                f"Video compilation completed with {total_duration:.1f}s duration (all available videos used)"
            )
        return YouTubeCompilationResult(clip=video, downloaded_bytes=downloaded_bytes)

    async def _finish_without_network(
        self,
        video: video_clip.VideoClip,
        downloaded_bytes: List[bytes],
        total_duration: float,
        remaining_ids: List[str],
        min_duration: int,
        low_quality: bool,
        throttle_error: YouTubeRateLimitError,
    ) -> YouTubeCompilationResult:
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
                "compilation has %.1fs of the %ds needed",
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

            downloaded_bytes.append(video_bytes)
            new_video.apply_anti_fingerprint(self._video_config.anti_fingerprint)
            video.concat(new_video)
            total_duration += duration

            if total_duration >= min_duration:
                logger.info(
                    "Compilation completed from local backgrounds despite the "
                    "throttle (%.1fs)",
                    total_duration,
                )
                return YouTubeCompilationResult(
                    clip=video, downloaded_bytes=downloaded_bytes
                )

        logger.error(
            "Local backgrounds were not enough: %.1fs of the %ds needed",
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

    def generate_video(
        self,
        audio: audio_clip.AudioClip,
        background_video: video_clip.VideoClip,
        low_quality: bool = False,
        cover: Optional[image_clip.ImageClip] = None,
        captions: Optional[captions_clip.CaptionsClip] = None,
        cta_start: float = 0,
    ) -> video_clip.VideoClip:
        """Generate final video with all components.

        The narration runs from the first frame; the cover sits on top of it
        for ``cover_duration`` seconds. The cover is deliberately narrower
        than the frame and the captions sit below it, so the opening subtitles
        stay readable while it is up. When *cta_start* is positive the
        configured CTA image is composited at that time.
        """
        config = self._video_config
        size_rate = 1.0
        if low_quality:
            size_rate = 400 / config.height
            config = config.model_copy(
                update=dict(
                    width=int(round(config.width * size_rate)),
                    height=int(round(config.height * size_rate)),
                    padding=int(round(config.padding * size_rate)),
                )
            )

        audio.add_end_silence(config.end_silece_seconds)
        background_video.resize(config.width, config.height)
        background_video.ajust_duration(audio.clip.duration)
        background_video.set_audio(audio)

        width, height = background_video.clip.size
        total_duration = audio.clip.duration
        fade = self.CROSSFADE_DURATION

        # --- cover ---
        if cover is not None:
            cover.fit_width(int(width * config.cover_width_ratio))
            cover.center(width, height)
            cover_dur = float(config.cover_duration)
            cover.set_duration(cover_dur)
            cover.apply_fadeout(min(0.3, cover_dur))
            background_video.merge(cover)

        # --- CTA image overlay ---
        if (
            self._call_to_action_bytes is not None
            and cta_start > 0
            and cta_start < total_duration
        ):
            cta_clip = image_clip.ImageClip(bytes=self._call_to_action_bytes)
            cta_clip.fit_width(width, config.padding)
            cta_clip.center(width, height)
            cta_clip.set_start(cta_start)
            cta_clip.set_duration(total_duration - cta_start)
            cta_clip.apply_fadein(fade)
            background_video.merge(cta_clip)

        # --- watermark ---
        if self._watermark_bytes is not None:
            water_mark = image_clip.ImageClip(bytes=self._watermark_bytes)
            water_mark.fit_width(width, config.padding)
            water_mark.center(width, height)
            water_mark.set_duration(total_duration)
            background_video.merge(water_mark)

        # --- captions ---
        if captions is not None:
            background_video.insert_captions(captions, size_rate=size_rate)
        return background_video

    CROSSFADE_DURATION = 0.5
    KEN_BURNS_MAX_SCALE = 1.12

    BRUSH_FEATHER = 0.06
    BRUSH_STROKE_COUNT = 4
