import random
from dataclasses import dataclass
from typing import Optional, List

from ..proxies.interfaces import IYouTubeProxy


from ..entities.editor import image_clip, audio_clip, video_clip, captions_clip
from ..core.logging_config import get_logger


@dataclass
class YouTubeCompilationResult:
    clip: video_clip.VideoClip
    downloaded_bytes: List[bytes]


class VideoService:
    """Video generation service implementation"""

    def __init__(
        self,
        youtube_proxy: IYouTubeProxy,
    ):
        self._logger = get_logger(__name__)
        self._youtube_proxy = youtube_proxy

    async def create_youtube_video_compilation(
        self, youtube_channel_url: str, min_duration: int, low_quality: bool = False
    ) -> YouTubeCompilationResult:
        """Create video compilation from YouTube content"""

        video_ids = await self._youtube_proxy.list_video_ids(youtube_channel_url)
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
            self._logger.info(f"total_duration: {total_duration}")
            self._logger.info(f"processed_videos: {processed_videos}")
            self._logger.info(f"min_duration: {min_duration}")

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
        video_width: int,
        video_height: int,
        end_silence_seconds: int = 3,
        padding: int = 60,
        cover_duration: int = 5,
        watermark_bytes: Optional[bytes] = None,
        cover: Optional[image_clip.ImageClip] = None,
        captions: Optional[captions_clip.CaptionsClip] = None,
    ) -> video_clip.VideoClip:
        """Generate final video with all components"""
        audio.add_end_silence(end_silence_seconds)
        background_video.resize(video_width, video_height)
        background_video.ajust_duration(audio.clip.duration)
        background_video.set_audio(audio)

        width, height = background_video.clip.size

        if cover is not None:
            cover.fit_width(width, padding)
            cover.center(width, height)
            cover.set_duration(cover_duration)
            cover.apply_fadeout(1)
            background_video.merge(cover)
        if watermark_bytes is not None:
            water_mark = image_clip.ImageClip(bytes=watermark_bytes)
            water_mark.fit_width(width, padding)
            water_mark.center(width, height)
            water_mark.set_duration(audio.clip.duration)
            background_video.merge(water_mark)
        if captions is not None:
            background_video.insert_captions(captions)
        return background_video
