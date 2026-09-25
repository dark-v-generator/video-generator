"""What any story writer promises: an origin in, a ``Story`` out."""

from typing import Optional, Protocol

from ...entities.language import Language
from ...entities.story import SpeechGender, Story, StoryOrigin


class WriterError(Exception):
    """The story could not be written."""


class WriterTransientError(WriterError):
    """A passing failure (rate limit, timeout, overloaded server): worth retrying."""


class WriterContentBlockedError(WriterError):
    """The model refused the content: retrying the same origin will not help."""


class StoryWriter(Protocol):
    async def write(
        self,
        origin: StoryOrigin,
        *,
        language: Language,
        speech_gender: Optional[SpeechGender] = None,
    ) -> Story: ...
