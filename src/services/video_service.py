import random
from dataclasses import dataclass
from typing import Optional, List

from ..proxies.interfaces import IYouTubeProxy
from ..entities.configs.services.video import VideoConfig


from ..entities.editor import image_clip, audio_clip, video_clip, captions_clip


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

    async def create_youtube_video_compilation(
        self, min_duration: int, low_quality: bool = False
    ) -> YouTubeCompilationResult:
        """Create video compilation from YouTube content"""

        video_ids = await self._youtube_proxy.list_video_ids(
            self._video_config.youtube_channel_url
        )
        random.shuffle(video_ids)

        video = video_clip.VideoClip()
        downloaded_bytes: List[bytes] = []
        total_duration = 0
        processed_videos = 0
        total_videos_to_process = min(len(video_ids), 2)

        for video_id in video_ids[:total_videos_to_process]:
            video_bytes = await self._youtube_proxy.download_video(
                video_id, low_quality
            )
            downloaded_bytes.append(video_bytes)

            new_video = video_clip.VideoClip(bytes=video_bytes)
            video.concat(new_video)
            total_duration += new_video.clip.duration
            processed_videos += 1

            if total_duration >= min_duration:
                return YouTubeCompilationResult(
                    clip=video, downloaded_bytes=downloaded_bytes
                )
        if total_duration < min_duration:
            raise Exception(
                f"Video compilation completed with {total_duration:.1f}s duration (all available videos used)"
            )
        return YouTubeCompilationResult(clip=video, downloaded_bytes=downloaded_bytes)

    def generate_video(
        self,
        audio: audio_clip.AudioClip,
        background_video: video_clip.VideoClip,
        low_quality: bool = False,
        cover: Optional[image_clip.ImageClip] = None,
        captions: Optional[captions_clip.CaptionsClip] = None,
    ) -> video_clip.VideoClip:
        """Generate final video with all components"""
        config = self._video_config
        size_rate = 1.0
        # Downscale config for preview natively inside VideoService
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

        if cover is not None:
            cover.fit_width(width, config.padding)
            cover.center(width, height)
            cover.set_duration(config.cover_duration)
            cover.apply_fadeout(1)
            background_video.merge(cover)
        if self._watermark_bytes is not None:
            water_mark = image_clip.ImageClip(bytes=self._watermark_bytes)
            water_mark.fit_width(width, config.padding)
            water_mark.center(width, height)
            water_mark.set_duration(audio.clip.duration)
            background_video.merge(water_mark)
        if captions is not None:
            background_video.insert_captions(captions, size_rate=size_rate)
        return background_video
