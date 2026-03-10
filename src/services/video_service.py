import random
from typing import Optional, AsyncIterable, Union

from ..adapters.proxies.interfaces import IYouTubeProxy


from ..adapters.repositories.interfaces import IFileStorage


from ..entities.editor import captions_clip
from .interfaces import IVideoService
from ..entities.editor import image_clip, audio_clip, video_clip
from ..entities.progress import ProgressEvent
from ..core.logging_config import get_logger


class VideoService(IVideoService):
    """Video generation service implementation"""

    def __init__(
        self,
        file_storage: IFileStorage,
        youtube_proxy: IYouTubeProxy,
    ):
        self._logger = get_logger(__name__)
        self._file_storage = file_storage
        self._youtube_proxy = youtube_proxy

    async def create_youtube_video_compilation(
        self, youtube_channel_url: str, min_duration: int, low_quality: bool = False
    ) -> AsyncIterable[Union[ProgressEvent, video_clip.VideoClip]]:
        """Create video compilation from YouTube content with streaming progress events"""
        yield ProgressEvent.create(
            "initializing",
            "Starting video compilation creation",
            details={"min_duration": min_duration},
        )

        video_ids = await self._youtube_proxy.list_video_ids(youtube_channel_url)
        random.shuffle(video_ids)

        video = video_clip.VideoClip()
        total_duration = 0
        processed_videos = 0
        total_videos_to_process = min(len(video_ids), 2)

        for video_id in video_ids[:total_videos_to_process]:
            yield ProgressEvent.create(
                "downloading",
                f"Downloading video {video_id}",
                progress=0,
                details={"video_id": video_id},
            )

            video_bytes = await self._youtube_proxy.download_video(
                video_id, low_quality
            )

            yield ProgressEvent.create(
                "downloading",
                f"Finished downloading video {video_id}",
                progress=100,
                details={"video_id": video_id},
            )

            new_video = video_clip.VideoClip(bytes=video_bytes)
            video.concat(new_video)
            total_duration += new_video.clip.duration
            processed_videos += 1
            self._logger.info(f"total_duration: {total_duration}")
            self._logger.info(f"processed_videos: {processed_videos}")
            self._logger.info(f"min_duration: {min_duration}")

            if total_duration >= min_duration:
                yield video
                return
        if total_duration < min_duration:
            raise Exception(
                f"Video compilation completed with {total_duration:.1f}s duration (all available videos used)"
            )
        yield video

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
