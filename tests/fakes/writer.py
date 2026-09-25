"""Fake story writer: one part, titled after the origin, no model involved."""

from typing import List, Optional

from src.entities.language import Language
from src.entities.story import SpeechGender, Story, StoryOrigin, StoryPart


class EchoStoryWriter:
    def __init__(self):
        self.origins: List[StoryOrigin] = []

    async def write(
        self,
        origin: StoryOrigin,
        *,
        language: Language,
        speech_gender: Optional[SpeechGender] = None,
    ) -> Story:
        self.origins.append(origin)
        return Story(
            title=origin.title,
            parts=[StoryPart(index=1, text=f"script for {origin.title}")],
            narrator_gender="unknown",
            resolved_gender=speech_gender or "male",
            language=language,
            summary="",
            origin=origin,
        )
