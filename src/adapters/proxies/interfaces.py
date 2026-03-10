from abc import ABC, abstractmethod
from typing import List

from ...entities.reddit_post import RedditPost
from ...entities.transcription import TranscriptionResult
from ...entities.language import Language
from ...entities.speech_voice import SpeechVoice
from typing import List, Optional, Literal, AsyncIterable


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


class ISpeechProxy(ABC):
    @abstractmethod
    async def generate_speech(
        self,
        text: str,
        gender: Literal["male", "female"] = "male",
        rate: float = 1.0,
        language: Language = Language.PORTUGUESE,
        override_voice_id: Optional[str] = None,
    ) -> bytes:
        """Generate speech bytes from text"""
        ...

    @abstractmethod
    def list_voices(self) -> List[SpeechVoice]:
        """List all available voices"""
        ...


class ILLMProxy(ABC):
    @abstractmethod
    async def translate_and_adapt(
        self, text: str, target_language: Language
    ) -> AsyncIterable[str]:
        """Translate and adapt text to the target language via LLM"""
        ...

    @abstractmethod
    async def generate_two_part_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        """Generate a 2-part TikTok story script from a Reddit post.
        Returns a dict with 'title', 'part1', and 'part2'."""
        ...
