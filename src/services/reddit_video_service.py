import shutil
import tempfile
import threading
from dataclasses import dataclass
from typing import AsyncIterable, Literal, Optional, Union

from ..proxies.interfaces import (
    ILLMProxy,
    IRedditProxy,
)
from ..core.logging_config import get_logger
from ..core.proglog_logger import AsyncProgressLogger
from ..entities.config import CaptionsConfig, VideoConfig
from ..entities.editor import image_clip, video_clip
from ..entities.editor.captions_clip import CaptionsClip
from ..entities.language import Language
from ..entities.progress import ProgressEvent
from .captions_service import CaptionsService
from .speech_service import SpeechService
from .video_service import VideoService


# ---------------------------------------------------------------------------
# Output data-class
# ---------------------------------------------------------------------------


@dataclass
class TwoPartVideoResult:
    """Paths to the two generated MP4 files."""

    part1_path: str
    part2_path: str


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RedditVideoService:
    """Generates a two-part Reddit-story video backed by YouTube compilation."""

    def __init__(
        self,
        reddit_proxy: IRedditProxy,
        llm_proxy: ILLMProxy,
        speech_service: SpeechService,
        captions_service: CaptionsService,
        video_service: VideoService,
    ) -> None:
        self._reddit_proxy = reddit_proxy
        self._llm_proxy = llm_proxy
        self._speech_service = speech_service
        self._captions_service = captions_service
        self._video_service = video_service
        self._logger = get_logger(__name__)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_two_part_history_video(
        self,
        *,
        post_url: str,
        output_path_part1: str,
        output_path_part2: str,
        language: Language = Language.PORTUGUESE,
        speech_gender: Literal["male", "female"] = "male",
        speech_rate: float = 1.0,
        youtube_channel_url: str,
        video_config: VideoConfig,
        captions_config: Optional[CaptionsConfig] = None,
        font_bytes: Optional[bytes] = None,
        cover_bytes: Optional[bytes] = None,
        watermark_bytes: Optional[bytes] = None,
        low_quality: bool = False,
    ) -> AsyncIterable[Union[ProgressEvent, TwoPartVideoResult]]:
        """Full pipeline: scrape → two-part story → speech → captions → videos.

        Yields :class:`ProgressEvent` objects throughout and finally yields a
        :class:`TwoPartVideoResult` with the paths to both MP4 files.
        """
        # ------------------------------------------------------------------ 1. Scrape
        yield ProgressEvent.create(
            "scraping", "Scraping Reddit post", details={"url": post_url}
        )
        post = self._reddit_proxy.get_reddit_post(post_url)
        self._logger.info("Scraped post: %s", post.title)

        # ------------------------------------------------------------------ 2. LLM: generate two-part story
        yield ProgressEvent.create(
            "story_generation",
            "Generating two-part story via LLM",
            details={"title": post.title},
        )
        story = await self._llm_proxy.generate_two_part_story(
            title=post.title,
            content=post.content,
            target_language=language,
        )
        part1_text: str = story["part1"]
        part2_text: str = story["part2"]
        self._logger.info(
            "Story split complete. Part1=%d chars, Part2=%d chars",
            len(part1_text),
            len(part2_text),
        )

        # ------------------------------------------------------------------ 3. Generate speech for both parts (returns SpeechResult)
        yield ProgressEvent.create("tts", "Generating speech for Part 1")
        speech_result_1 = await self._speech_service.generate_speech(
            text=part1_text,
            gender=speech_gender,
            rate=speech_rate,
            language=language,
        )

        yield ProgressEvent.create("tts", "Generating speech for Part 2")
        speech_result_2 = await self._speech_service.generate_speech(
            text=part2_text,
            gender=speech_gender,
            rate=speech_rate,
            language=language,
        )

        # ------------------------------------------------------------------ 4. Transcribe + enhance captions (returns CaptionsResult)
        yield ProgressEvent.create("transcription", "Transcribing Part 1")
        captions_result_1 = await self._captions_service.generate_captions(
            audio_bytes=speech_result_1.bytes,
            enhance_captions=True,
            language=language,
            base_text=part1_text,
        )

        yield ProgressEvent.create("transcription", "Transcribing Part 2")
        captions_result_2 = await self._captions_service.generate_captions(
            audio_bytes=speech_result_2.bytes,
            enhance_captions=True,
            language=language,
            base_text=part2_text,
        )

        # ------------------------------------------------------------------ 5. Generate videos
        yield ProgressEvent.create("video", "Generating video for Part 1")
        async for event in self._generate_single_video(
            speech=speech_result_1.clip,
            captions_clip_obj=captions_result_1.clip,
            cover_bytes=cover_bytes,
            watermark_bytes=watermark_bytes,
            youtube_channel_url=youtube_channel_url,
            video_config=video_config,
            captions_config=captions_config,
            output_path=output_path_part1,
            low_quality=low_quality,
        ):
            yield event

        yield ProgressEvent.create("video", "Generating video for Part 2")
        async for event in self._generate_single_video(
            speech=speech_result_2.clip,
            captions_clip_obj=captions_result_2.clip,
            cover_bytes=cover_bytes,
            watermark_bytes=watermark_bytes,
            youtube_channel_url=youtube_channel_url,
            video_config=video_config,
            captions_config=captions_config,
            output_path=output_path_part2,
            low_quality=low_quality,
        ):
            yield event

        yield TwoPartVideoResult(
            part1_path=output_path_part1, part2_path=output_path_part2
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _generate_single_video(
        self,
        *,
        speech,
        captions_clip_obj: Optional[CaptionsClip],
        cover_bytes: Optional[bytes],
        watermark_bytes: Optional[bytes],
        youtube_channel_url: str,
        video_config: VideoConfig,
        captions_config: Optional[CaptionsConfig],
        output_path: str,
        low_quality: bool,
    ) -> AsyncIterable[Union[ProgressEvent, str]]:
        """Compile a single video from speech + captions + YouTube background."""
        # Downscale config for preview
        if low_quality:
            size_rate = 400 / video_config.height
            video_config = video_config.model_copy(
                update=dict(
                    width=int(round(video_config.width * size_rate)),
                    height=int(round(video_config.height * size_rate)),
                    padding=int(round(video_config.padding * size_rate)),
                )
            )

        cover = image_clip.ImageClip(bytes=cover_bytes) if cover_bytes else None

        # Download YouTube compilation background
        yield ProgressEvent.create("downloading", "Downloading YouTube compilation background")
        compilation_result = await self._video_service.create_youtube_video_compilation(
            youtube_channel_url=youtube_channel_url,
            min_duration=speech.clip.duration,
            low_quality=low_quality,
        )
        background_video = compilation_result.clip

        if background_video is None:
            raise RuntimeError("Failed to create background video compilation.")

        # Compose
        yield ProgressEvent.create("composing", "Composing final video")
        final_video = self._video_service.generate_video(
            audio=speech,
            background_video=background_video,
            video_width=video_config.width,
            video_height=video_config.height,
            end_silence_seconds=video_config.end_silece_seconds,
            padding=video_config.padding,
            cover_duration=video_config.cover_duration,
            watermark_bytes=watermark_bytes,
            cover=cover,
            captions=captions_clip_obj,
        )

        # Write to disk on a background thread
        progress_logger = AsyncProgressLogger("video_writing", "Writing video file")
        write_error: Optional[Exception] = None

        def _write_thread() -> None:
            nonlocal write_error
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                    tmp_path = tmp.name
                final_video.clip.write_videofile(
                    tmp_path,
                    ffmpeg_params=video_config.ffmpeg_params,
                    logger=progress_logger,
                )
                progress_logger.finish_progress()
                shutil.move(tmp_path, output_path)
            except Exception as exc:
                write_error = exc
                progress_logger.finish_progress()

        thread = threading.Thread(target=_write_thread, daemon=True)
        thread.start()

        while not progress_logger.is_finished():
            event = await progress_logger.get_progress_event()
            if event:
                yield event

        thread.join()

        if write_error:
            raise write_error

        self._logger.info("Video written to %s", output_path)
