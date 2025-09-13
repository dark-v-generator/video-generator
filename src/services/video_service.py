import os
import random
import tempfile
import threading
from typing import Optional, AsyncIterable, Union

from googleapiclient.discovery import build
from pytubefix import YouTube

from ..adapters.repositories.interfaces import IConfigRepository
from ..adapters.repositories.interfaces import IFileStorage


from ..core.proglog_logger import AsyncProgressLogger
from ..entities.config import VideoConfig
from ..entities.editor import captions_clip
from .interfaces import IVideoService
from ..entities.editor import image_clip, audio_clip, video_clip
from ..entities.progress import ProgressEvent
from ..core.logging_config import get_logger
from ..core.config import settings


class VideoService(IVideoService):
    """Video generation service implementation"""

    def __init__(
        self, config_repository: IConfigRepository, file_storage: IFileStorage
    ):
        self._config_repository = config_repository
        self._logger = get_logger(__name__)
        self._file_storage = file_storage

    def _get_youtube_service(self):
        if not settings.youtube_api_key:
            raise Exception("YouTube API key is not set")
        return build("youtube", "v3", developerKey=settings.youtube_api_key)

    async def create_video_compilation(
        self, min_duration: int, low_quality: bool = False
    ) -> AsyncIterable[Union[ProgressEvent, video_clip.VideoClip]]:
        """Create video compilation from YouTube content with streaming progress events"""
        yield ProgressEvent.create(
            "initializing",
            "Starting video compilation creation",
            details={"min_duration": min_duration},
        )

        config = self._config_repository.load_config()

        video_ids = self._get_video_ids(
            config.video_config.youtube_channel_id, max_results=500
        )
        random.shuffle(video_ids)

        video = video_clip.VideoClip()
        total_duration = 0
        processed_videos = 0
        total_videos_to_process = min(len(video_ids), 2)

        for video_id in video_ids[:total_videos_to_process]:
            async for event in self._download_youtube_video(
                video_id, low_quality=low_quality
            ):
                if isinstance(event, ProgressEvent):
                    yield event
                else:

                    new_video = video_clip.VideoClip(bytes=event)
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
        cover: Optional[image_clip.ImageClip] = None,
        captions: Optional[captions_clip.CaptionsClip] = None,
        low_quality: bool = False,
    ) -> video_clip.VideoClip:
        """Generate final video with all components"""
        config = self._config_repository.load_config()

        if low_quality:
            size_rate = 400 / config.video_config.height
            config.video_config.width = int(
                round(config.video_config.width * size_rate)
            )
            config.video_config.height = int(
                round(config.video_config.height * size_rate)
            )
            config.captions_config.font_size = int(
                round(config.captions_config.font_size * size_rate)
            )
            config.captions_config.stroke_width = int(
                round(config.captions_config.stroke_width * size_rate)
            )
            config.captions_config.marging = int(
                round(config.captions_config.marging * size_rate)
            )
            config.video_config.padding = int(
                round(config.video_config.padding * size_rate)
            )

        audio.add_end_silence(config.video_config.end_silece_seconds)
        background_video.resize(config.video_config.width, config.video_config.height)
        background_video.ajust_duration(audio.clip.duration)
        background_video.set_audio(audio)

        width, height = background_video.clip.size
        water_mark_bytes = self._file_storage.load_file(
            config.video_config.watermark_file_id
        )

        if cover is not None:
            cover.fit_width(width, config.video_config.padding)
            cover.center(width, height)
            cover.set_duration(config.video_config.cover_duration)
            cover.apply_fadeout(1)
            background_video.merge(cover)
        if water_mark_bytes is not None:
            water_mark = image_clip.ImageClip(bytes=water_mark_bytes)
            water_mark.fit_width(width, config.video_config.padding)
            water_mark.center(width, height)
            water_mark.set_duration(audio.clip.duration)
            background_video.merge(water_mark)
        if captions is not None:
            background_video.insert_captions(captions)
        return background_video

    def _get_video_ids(self, channel_id, max_results=500):
        youtube_service = self._get_youtube_service()
        search_request = youtube_service.search().list(
            part="id", channelId=channel_id, maxResults=max_results
        )
        search_response = search_request.execute()
        video_ids = []
        for item in search_response.get("items", []):
            if item["id"]["kind"] == "youtube#video":
                video_ids.append(item["id"]["videoId"])
        return video_ids

    async def _download_youtube_video(
        self,
        video_id: str,
        low_quality=False,
    ) -> AsyncIterable[Union[ProgressEvent, bytes]]:
        yt = YouTube(
            f"https://www.youtube.com/watch?v={video_id}",
            "WEB_CREATOR",
            use_oauth=True,
        )

        progress_logger = AsyncProgressLogger(
            stage="downloading_youtube_video",
            message=f"Downloading: {yt.title}",
        )

        def progress_callback(stream, chunk, bytes_remaining):
            # This runs in the download thread, so we put events in the queue
            progress = 100 - (bytes_remaining / stream.filesize) * 100
            self._logger.info(f"Download progress: {progress:.1f}% - {stream.title}")

            event = ProgressEvent.create(
                "downloading",
                f"Downloading video {stream.title}",
                progress=progress,
                details={
                    "video_id": video_id,
                    "bytes_remaining": bytes_remaining,
                    "filesize": stream.filesize,
                },
            )
            progress_logger.put_progress_event(event)

        yt.register_on_progress_callback(progress_callback)
        streams = yt.streams.filter(only_video=True).order_by("bitrate").desc()
        if not streams:
            raise Exception(f"No video streams found for {video_id}")
        if low_quality:
            stream = streams.last()
        else:
            stream = streams.first()

        video_bytes = None

        def download_thread():
            nonlocal video_bytes
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmpfile:
                output_path = os.path.dirname(tmpfile.name)
                filename = os.path.basename(tmpfile.name)

                stream.download(
                    output_path=output_path,
                    filename=filename,
                    skip_existing=False,
                )
                progress_logger.finish_progress()

                with open(tmpfile.name, "rb") as f:
                    video_bytes = f.read()

        thread = threading.Thread(target=download_thread)
        thread.start()

        while not progress_logger.is_finished():
            event = await progress_logger.get_progress_event()
            if event:
                yield event

        thread.join()

        if video_bytes:
            yield video_bytes
        else:
            raise Exception(f"No video data received for {video_id}")
