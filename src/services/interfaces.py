from abc import ABC, abstractmethod
from typing import List, Optional, AsyncIterable, Union

from ..entities.speech_voice import SpeechVoice

from ..entities.editor.captions_clip import CaptionsClip

from ..entities.reddit_history import RedditHistory
from ..entities.language import Language
from ..entities.captions import Captions
from ..entities.cover import RedditCover
from ..entities.editor.audio_clip import AudioClip
from ..entities.editor.image_clip import ImageClip
from ..entities.editor.video_clip import VideoClip
from ..entities.progress import ProgressEvent
from ..entities.config import MainConfig


class IConfigService(ABC):
    @abstractmethod
    def get_config(self) -> MainConfig:
        """Get the configuration"""
        ...

    def save_config(self, config: MainConfig) -> None:
        """Save the configuration"""
        ...

    def save_watermark(self, file_content: bytes) -> str:
        """Save the watermark file"""
        ...

    def save_font(self, file_content: bytes) -> str:
        """Save the font file"""
        ...


class IHistoryService(ABC):
    @abstractmethod
    async def srcap_reddit_post(
        self,
        post_url: str,
        language: Language = Language.PORTUGUESE,
    ) -> RedditHistory:
        """Scrape a Reddit post and create history"""
        pass

    @abstractmethod
    def list_histories(self) -> List[RedditHistory]:
        """List all available histories"""
        pass

    @abstractmethod
    def get_reddit_history(self, history_id: str) -> RedditHistory:
        """Get a specific Reddit history by ID"""
        pass

    @abstractmethod
    def save_reddit_history(self, reddit_history: RedditHistory) -> None:
        """Save Reddit history to storage"""
        pass

    @abstractmethod
    def delete_reddit_history(self, history_id: str) -> bool:
        """Delete a Reddit history"""
        pass

    @abstractmethod
    async def generate_speech(
        self,
        reddit_history: RedditHistory,
        rate: float,
        voice_id: str,
    ) -> AsyncIterable[Union[ProgressEvent, RedditHistory]]:
        """Generate speech for history with streaming progress events"""
        pass

    @abstractmethod
    async def generate_captions(
        self,
        history_id: str,
        rate: float,
        enhance_captions: bool,
    ) -> None:
        """Generate captions for history"""
        pass

    @abstractmethod
    def generate_cover(
        self, reddit_history: RedditHistory
    ) -> AsyncIterable[Union[ProgressEvent, RedditHistory]]:
        """Generate cover image for history"""
        pass

    @abstractmethod
    async def generate_reddit_video(
        self,
        reddit_history: RedditHistory,
        low_quality: bool = False,
    ) -> AsyncIterable[Union[ProgressEvent, RedditHistory]]:
        """Generate final video for Reddit history with streaming progress events"""
        pass


class ISpeechService(ABC):
    @abstractmethod
    async def generate_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        rate: float = 1.0,
    ) -> bytes:
        """Generate speech from text with progress events, yielding audio bytes as final result"""
        ...

    @abstractmethod
    def list_voices(self) -> List[SpeechVoice]:
        """List all available voices"""
        ...


class ICaptionsService(ABC):
    @abstractmethod
    async def generate_captions(
        self,
        audio_file_id: str,
        enhance_captions: bool = False,
        language: Language = Language.PORTUGUESE,
    ) -> Captions:
        """Generate captions from audio"""
        pass


class ICoverService(ABC):
    @abstractmethod
    async def generate_cover(self, cover: RedditCover) -> bytes:
        """Generate cover image and return PNG bytes"""
        pass


class IVideoService(ABC):
    @abstractmethod
    def generate_video(
        self,
        audio: AudioClip,
        background_video: VideoClip,
        cover: Optional[ImageClip] = None,
        captions: Optional[CaptionsClip] = None,
        low_quality: bool = False,
    ) -> VideoClip:
        """Generate final video with all components"""
        pass

    @abstractmethod
    def create_video_compilation(
        self, min_duration: int, low_quality: bool = False
    ) -> AsyncIterable[Union[ProgressEvent, VideoClip]]:
        """Create video compilation from YouTube content with streaming progress events"""
        pass
