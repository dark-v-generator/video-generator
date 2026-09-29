from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional, Literal, Sequence

from ..entities.history import PerformanceMetrics, TikTokVideoStats
from ..entities.reddit_post import RedditPost
from ..entities.transcription import TranscriptionResult
from ..entities.language import Language
from ..entities.speech_voice import SpeechVoice
from ..entities.tuning import Experiment


class RedditPostUnavailableError(ValueError):
    """The post was deleted, removed or made private; Reddit answers, the
    post is just not there any more."""


class IRedditProxy(ABC):
    @abstractmethod
    def get_reddit_post(self, url: str) -> RedditPost:
        """Get a Reddit post from a URL.

        Raises ``RedditPostUnavailableError`` for a post that is gone; any
        other failure (network, rate limit, blocked request) raises as is.
        """
        ...

    @abstractmethod
    def list_subreddit_posts(
        self,
        subreddit: str,
        sort: Literal["top", "new", "hot"] = "top",
        time_filter: Literal["hour", "day", "week", "month", "year", "all"] = "day",
        limit: int = 25,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> List[RedditPost]:
        """List posts from a subreddit with optional filters.

        Args:
            subreddit: Subreddit name without the r/ prefix.
            sort: Sort order — 'top', 'new', or 'hot'.
            time_filter: Time window for 'top' sort — 'hour', 'day', 'week', 'month', 'year', 'all'.
            limit: Maximum number of posts to return (after filtering).
            min_chars: If set, exclude posts with fewer content characters.
            max_chars: If set, exclude posts with more content characters.
        """
        ...


class ITranscriptionProxy(ABC):
    @abstractmethod
    def transcribe(
        self, audio_bytes: bytes, language: Optional[Language] = None
    ) -> TranscriptionResult:
        """Generate transcription result from audio bytes"""
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
    def voice_id(self, gender: Literal["male", "female"], language: Language) -> str:
        """The voice ``generate_speech`` narrates with, without an override."""
        ...

    @abstractmethod
    def list_voices(self) -> List[SpeechVoice]:
        """List all available voices"""
        ...


class ILLMProxy(ABC):
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
    async def evaluate_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        """Evaluate a Reddit post for TikTok potential.
        Returns a dict with 'resumo', 'notas' (per-criterion grades + justificativas),
        'nota_geral', and 'veredito'."""
        ...

    @abstractmethod
    async def evaluate_exploration(
        self,
        title: str,
        content: str,
        experiments: Sequence[Experiment],
        target_language: Language,
    ) -> dict:
        """Which of the open *experiments* a Reddit post is a fair test of.
        Returns ``{"experiment": id or None, "fit": 0-100, "reason": str}``;
        an id that was not given or a fit off the scale raises ValueError."""
        ...

    @abstractmethod
    async def generate_hashtags(
        self, title: str, summary: str, target_language: Language
    ) -> List[str]:
        """Generate TikTok hashtags relevant to a story.
        Returns a list of hashtag strings without the leading '#'."""
        ...


class IYouTubeProxy(ABC):
    @abstractmethod
    async def list_video_ids(
        self,
        url: str,
        surface: Literal["videos", "shorts"] = "videos",
    ) -> List[str]:
        """List video IDs from a YouTube channel or playlist URL"""
        ...

    @abstractmethod
    async def download_video(self, video_id: str, low_quality: bool = False) -> bytes:
        """Download a YouTube video and return its bytes"""
        ...

    def locally_available(
        self, video_ids: List[str], low_quality: bool = False
    ) -> List[str]:
        """Which of *video_ids* can be served without going to the network.

        Callers use this to keep working when YouTube is unreachable. An
        implementation that always needs the network answers with nothing,
        which is the default here, so a plain proxy behaves exactly as before.
        """
        return []


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


class ITikTokPublisherProxy(ABC):
    @abstractmethod
    async def publish_video(
        self,
        video_path: str,
        description: str,
        hashtags: Optional[List[str]] = None,
        schedule_at: Optional[datetime] = None,
    ) -> str:
        """Publish — or schedule — a video file to TikTok via an AI agent.

        The proxy is responsible for logging in (using stored credentials),
        persisting the session cookies between runs, navigating to the upload
        page, attaching the video, and filling the description. If
        ``schedule_at`` is provided the agent toggles TikTok Studio's
        "Schedule video" option and sets the date/time before clicking
        "Schedule". TikTok only allows scheduling up to 10 days in the
        future on Creator/Business accounts; the implementation should
        reject anything outside that window. Returns the URL of the
        published video when available, otherwise an empty string.
        """
        ...


class TikTokSessionExpiredError(RuntimeError):
    """The TikTok profile is logged out; the Studio sent us to the login page."""


class TikTokStudioLayoutError(RuntimeError):
    """A Studio response lacks a field the reader depends on.

    The message names the field and the endpoint, so the fix is to rerun
    ``scripts/tiktok_studio_probe.py`` and adjust the parser to the new dump.
    """


class ITikTokStudioProxy(ABC):
    """Reads the account's own numbers from the TikTok Studio.

    One browser serves every call until ``close`` (or the end of an
    ``async with``), so a collection opens the profile once.
    """

    @abstractmethod
    async def list_videos(self, *, since: datetime) -> List[TikTokVideoStats]:
        """The account's posts created at or after ``since``, with the counts
        the content list shows. An empty list is a valid answer."""
        ...

    @abstractmethod
    async def video_analytics(self, video_id: str) -> PerformanceMetrics:
        """One video's analytics: the list counts plus retention. A metric
        the Studio does not return for this video is ``None``."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release the browser; the profile stays locked until this runs."""
        ...

    async def __aenter__(self) -> "ITikTokStudioProxy":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()
