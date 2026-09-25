"""Writes a one-part story by asking a language model to adapt the origin."""

from typing import Optional

import litellm

from ...entities.language import Language
from ...entities.story import SpeechGender, Story, StoryOrigin, StoryPart
from ...proxies.interfaces import ILLMProxy
from .contract import WriterContentBlockedError, WriterError, WriterTransientError

_CONTENT_BLOCKED_SIGNALS = (
    "safety filter",
    "content filter",
    "nsfw",
    "blocked",
    "content policy",
)
_TRANSIENT_SIGNALS = (
    "429",
    "rate limit",
    "too many requests",
    "timeout",
    "503",
    "502",
)


def classify_error(exc: Exception) -> WriterError:
    """Translate a model client failure into what the caller can act on.

    A refusal is checked first: a provider that blocks content may answer with
    a status that also looks transient, and retrying a refusal only wastes time.
    """
    message = str(exc)
    lowered = message.lower()
    if any(signal in lowered for signal in _CONTENT_BLOCKED_SIGNALS):
        return WriterContentBlockedError(message)
    if isinstance(exc, litellm.RateLimitError) or any(
        signal in lowered for signal in _TRANSIENT_SIGNALS
    ):
        return WriterTransientError(message)
    return WriterError(message)


class ModelStoryWriter:
    def __init__(self, llm: ILLMProxy) -> None:
        self._llm = llm

    async def write(
        self,
        origin: StoryOrigin,
        *,
        language: Language,
        speech_gender: Optional[SpeechGender] = None,
    ) -> Story:
        try:
            written = await self._llm.generate_story(
                title=origin.title,
                content=origin.content,
                target_language=language,
            )
        except Exception as e:
            raise classify_error(e) from e

        narrator_gender = written.get("narrator_gender", "unknown")
        if narrator_gender not in ("male", "female"):
            narrator_gender = "unknown"

        return Story(
            title=written.get("title", origin.title),
            parts=[StoryPart(index=1, text=written["script"])],
            narrator_gender=narrator_gender,
            resolved_gender=speech_gender
            or (narrator_gender if narrator_gender != "unknown" else "male"),
            language=language,
            summary="",
            origin=origin,
        )
