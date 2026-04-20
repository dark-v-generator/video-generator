import datetime
from abc import ABC, abstractmethod
from typing import List, Optional, Literal

from ..entities.image_story import ImageStory
from ..entities.reddit_post import RedditPost
from ..entities.transcription import TranscriptionResult
from ..entities.language import Language
from ..entities.speech_voice import SpeechVoice


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
        character_references: dict[str, bytes] | None = None,
    ) -> List[bytes]:
        """Generate a list of images from a prompt.

        character_references: optional mapping of character name → portrait PNG bytes.
        Backends that support character conditioning (e.g. Leonardo Phoenix) will use
        these as visual references; others silently ignore them.
        """
        ...


class IVideoGeneratorProxy(ABC):
    @abstractmethod
    def generate_video(
        self,
        prompt: str,
        reference_image: bytes,
        width: int = 1360,
        height: int = 768,
    ) -> bytes:
        """Generate a video from a prompt using a reference image. Returns video bytes."""
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
    async def generate_two_part_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        """Generate a 2-part TikTok story script from a Reddit post.
        Returns a dict with 'title', 'part1', and 'part2'."""
        ...

    @abstractmethod
    async def generate_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        """Generate a single TikTok story script from a Reddit post.
        Returns a dict with 'title', 'narrator_gender', and 'script'."""
        ...

    @abstractmethod
    async def enhance_transcription(
        self, base_text: str, raw_transcription: List[dict]
    ) -> List[dict]:
        """Enhance a raw transcription word list using a base script as ground truth.
        Returns the corrected list of dictionaries with 'word', 'start', 'end', 'probability'.
        """
        ...

    @abstractmethod
    async def revise_story(
        self, current_script: dict, feedback: str, target_language: Language
    ) -> dict:
        """Revise an existing two-part story script based on user feedback.
        Returns a dict with the same shape as generate_two_part_story."""
        ...

    @abstractmethod
    async def generate_characters(
        self, title: str, part1: str, part2: str, target_language: Language
    ) -> list[dict]:
        """Extract characters from a story and return visual descriptions.
        Returns a list of dicts: [{"name": str, "description": str, "visual_prompt": str}]."""
        ...

    @abstractmethod
    async def evaluate_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        """Evaluate a Reddit post for TikTok potential.
        Returns a dict with 'resumo', 'notas' (per-criterion grades + justificativas),
        'nota_geral', and 'veredito'."""
        ...

    @abstractmethod
    async def generate_image_story(
        self,
        story_text: str,
        transcription: List[dict],
        style_context: Optional[str] = None,
        characters: Optional[list[dict]] = None,
        introduction_end_time: float = 0.0,
        call_to_action_start_time: float = 0.0,
    ) -> ImageStory:
        """Generate timed scene images for the content portion of a narrated story.
        introduction_end_time and call_to_action_start_time are pre-computed by
        the caller; the LLM only generates the images array."""
        ...


class IYouTubeProxy(ABC):
    @abstractmethod
    async def list_video_ids(self, url: str) -> List[str]:
        """List video IDs from a YouTube channel or playlist URL"""
        ...

    @abstractmethod
    async def download_video(self, video_id: str, low_quality: bool = False) -> bytes:
        """Download a YouTube video and return its bytes"""
        ...


class ITikTokProxy(ABC):
    @abstractmethod
    def upload_video(
        self,
        video_path: str,
        description: str,
        schedule: Optional[datetime.datetime] = None,
    ) -> None:
        """Upload a video to TikTok, optionally scheduling it.
        schedule must be a UTC datetime at least 20min in the future and at most 10 days."""
        ...


class ICoverProxy(ABC):
    @abstractmethod
    async def create_reddit_cover(
        self,
        title: str,
        community: str,
        author: str,
        community_url_photo: str,
    ) -> bytes:
        """Generate a reddit cover image and return PNG bytes"""
        ...
