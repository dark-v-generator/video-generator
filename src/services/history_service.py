import tempfile
import threading
from typing import List, AsyncIterable, Union
import uuid

from ..core.proglog_logger import AsyncProgressLogger
from ..core.logging_config import get_logger

from .interfaces import (
    IHistoryService,
    ISpeechService,
    ICaptionsService,
    ICoverService,
    IVideoService,
)
from .llm.interfaces import ILLMService
from ..entities.captions import Captions
from ..entities.config import MainConfig
from ..entities.cover import RedditCover
from ..entities.editor import audio_clip, captions_clip, image_clip
from ..entities.history import History
from ..entities.language import Language
from ..models.progress import ProgressEvent
from ..entities.reddit_history import RedditHistory
from ..repositories.interfaces import (
    IFileStorage,
    IHistoryRepository,
    IFileRepository,
    IConfigRepository,
)
from ..proxies import reddit_proxy


class HistoryService(IHistoryService):
    """History service implementation with dependency injection"""

    def __init__(
        self,
        history_repository: IHistoryRepository,
        config_repository: IConfigRepository,
        speech_service: ISpeechService,
        captions_service: ICaptionsService,
        cover_service: ICoverService,
        video_service: IVideoService,
        llm_service: ILLMService,
        file_storage: IFileStorage,
    ):
        self._history_repository = history_repository
        self._config_repository = config_repository
        self._speech_service = speech_service
        self._captions_service = captions_service
        self._cover_service = cover_service
        self._video_service = video_service
        self._llm_service = llm_service
        self._file_storage = file_storage
        self._logger = get_logger(__name__)

    def _get_config(self) -> MainConfig:
        return self._config_repository.load_config()

    async def srcap_reddit_post(
        self,
        post_url: str,
        language: Language = Language.PORTUGUESE,
    ) -> RedditHistory:
        """Scrape a Reddit post and create history"""
        reddit_post = reddit_proxy.get_reddit_post(post_url)
        history = History(title=reddit_post.title, content=reddit_post.content)
        cover = RedditCover(
            image_url=reddit_post.community_url_photo,
            author=reddit_post.author,
            community=reddit_post.community,
            title=history.title,
        )
        reddit_history = RedditHistory(
            id=str(uuid.uuid4()),
            cover=cover,
            history=history.striped(),
            language=language.value,
        )
        self._history_repository.save_reddit_history(reddit_history)
        return reddit_history

    def list_histories(self) -> List[RedditHistory]:
        """List all available histories"""
        history_ids = self._history_repository.list_history_ids()
        histories = []
        for history_id in history_ids:
            history = self._history_repository.load_reddit_history(history_id)
            if history is not None:
                histories.append(history)
        return sorted(histories, key=lambda x: x.last_updated_at, reverse=True)

    def get_reddit_history(self, history_id: str) -> RedditHistory:
        """Get a specific Reddit history by ID"""
        return self._history_repository.load_reddit_history(history_id)

    def save_reddit_history(self, reddit_history: RedditHistory) -> None:
        """Save Reddit history to storage"""
        self._history_repository.save_reddit_history(reddit_history)

    def delete_reddit_history(self, history_id: str) -> bool:
        """Delete a Reddit history"""
        return self._history_repository.delete_reddit_history(history_id)

    async def generate_speech(
        self,
        reddit_history: RedditHistory,
        rate: float,
        voice_id: str,
    ) -> AsyncIterable[Union[ProgressEvent, RedditHistory]]:
        """Generate speech for history with streaming progress events"""
        history = reddit_history.history
        text = self._get_speech_text(history)
        yield ProgressEvent.create(
            "generating",
            "Generating speech",
            details={"text_length": len(text), "rate": rate},
        )
        speech_bytes = await self._speech_service.generate_speech(text, voice_id, rate)
        yield ProgressEvent.create(
            "saving",
            "Saving audio file",
        )
        self._history_repository.save_speech_file(reddit_history.id, speech_bytes)
        yield self._history_repository.load_reddit_history(reddit_history.id)

    async def generate_captions(
        self,
        history_id: str,
        rate: float,
        enhance_captions: bool,
    ) -> None:
        """Generate captions for history"""
        self._logger.info("Generating captions...")

        reddit_history = self._history_repository.load_reddit_history(history_id)
        captions = await self._captions_service.generate_captions(
            reddit_history.speech_file_id,
            enhance_captions=enhance_captions,
            language=reddit_history.get_language(),
        )
        self._history_repository.save_captions_file(
            history_id=reddit_history.id, captions_bytes=captions.to_bytes()
        )

    async def generate_cover(
        self, reddit_history: RedditHistory
    ) -> AsyncIterable[Union[ProgressEvent, RedditHistory]]:
        """Generate cover image for history"""
        yield ProgressEvent.create(
            "starting",
            "Generating cover",
            details={
                "title": (
                    reddit_history.history.title[:50] + "..."
                    if len(reddit_history.history.title) > 50
                    else reddit_history.history.title
                )
            },
        )

        cover_bytes = await self._cover_service.generate_cover(reddit_history.cover)
        if not cover_bytes:
            raise Exception("No cover data received from cover service")

        yield ProgressEvent.create(
            "saving",
            "Saving cover file",
        )
        self._history_repository.save_cover_file(
            history_id=reddit_history.id, cover_bytes=cover_bytes
        )

        yield self._history_repository.load_reddit_history(reddit_history.id)

    async def generate_reddit_video(
        self,
        reddit_history: RedditHistory,
        low_quality: bool = False,
    ) -> AsyncIterable[Union[ProgressEvent, RedditHistory]]:
        config = self._config_repository.load_config()
        """Generate final video for Reddit history with streaming progress events"""
        yield ProgressEvent.create(
            "initializing",
            "Starting video generation",
            details={"history_id": reddit_history.id, "low_quality": low_quality},
        )

        # Apply low quality settings
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

        # Load components
        speech_bytes = self._history_repository.get_speech_bytes(reddit_history.id)
        captions_bytes = self._history_repository.get_captions_bytes(reddit_history.id)
        cover_bytes = self._history_repository.get_cover_bytes(reddit_history.id)
        font_bytes = self._get_font_bytes()

        if not speech_bytes:
            raise Exception("No speech audio available for video generation")

        speech = audio_clip.AudioClip(bytes=speech_bytes)
        captions = (
            captions_clip.CaptionsClip(
                captions=Captions.from_bytes(captions_bytes),
                config=config.captions_config,
                font_bytes=font_bytes,
            )
            if captions_bytes and font_bytes
            else None
        )
        cover = image_clip.ImageClip(bytes=cover_bytes) if cover_bytes else None

        background_video = None
        async for event in self._video_service.create_video_compilation(
            speech.clip.duration, low_quality=low_quality
        ):
            if isinstance(event, ProgressEvent):
                yield event
            else:
                background_video = event

        if not background_video:
            raise Exception("Failed to create background video")

        yield ProgressEvent.create(
            "generating",
            "Generating final video",
            details={
                "components": [
                    "audio",
                    "background",
                    "cover" if cover else None,
                    "captions" if captions else None,
                ]
            },
        )

        final_video = self._video_service.generate_video(
            audio=speech,
            background_video=background_video,
            cover=cover,
            low_quality=low_quality,
            captions=captions,
        )

        progress_logger = AsyncProgressLogger(
            "video_writing",
            "Generating final video",
        )

        final_video_bytes = None

        def final_video_thread():
            nonlocal final_video_bytes
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmpfile:
                absolute_video_path = tmpfile.name
                final_video.clip.write_videofile(
                    absolute_video_path,
                    ffmpeg_params=config.video_config.ffmpeg_params,
                    logger=progress_logger,
                )
                progress_logger.finish_progress()
                with open(absolute_video_path, "rb") as f:
                    final_video_bytes = f.read()

        thread = threading.Thread(target=final_video_thread)
        thread.start()

        while not progress_logger.is_finished():
            event = await progress_logger.get_progress_event()
            if event:
                yield event

        thread.join()

        if not final_video_bytes:
            raise Exception("Failed to generate final video")

        self._history_repository.save_final_video_file(
            history_id=reddit_history.id, final_video_bytes=final_video_bytes
        )
        yield self._history_repository.load_reddit_history(reddit_history.id)

    def _get_speech_text(self, history: History) -> str:
        """Get text for speech synthesis"""
        return history.content

    def _get_font_bytes(self) -> bytes:
        """Get font bytes from storage"""
        font_id = self._config_repository.load_config().captions_config.font_file_id
        if not font_id:
            with open("default_font.ttf", "rb") as f:
                font_bytes = f.read()
            return font_bytes
        return self._file_storage.load_file(font_id)
