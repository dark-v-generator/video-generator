from abc import ABC, abstractmethod
from typing import List

from ...entities.reddit import RedditPost
from ...entities.transcription import TranscriptionResult
from ...entities.language import Language
from typing import List, Optional


class IRedditProxy(ABC):
    @abstractmethod
    def get_reddit_post(self, url: str) -> RedditPost:
        """Get a Reddit post from a URL"""
        ...


class ITranscriptionProxy(ABC):
    @abstractmethod
    def transcribe(
        self, audio_bytes: bytes, language: Optional[Language] = None
    ) -> TranscriptionResult:
        """Generate transcription result from audio bytes"""
        ...


class IImageGeneratorProxy(ABC):
    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
    ) -> List[bytes]:
        """Generate a list of images from a prompt"""
        ...
