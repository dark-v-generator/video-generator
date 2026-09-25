"""Hands back stories that were already written, without calling any model."""

import dataclasses
from typing import Optional

from ...entities.language import Language
from ...entities.story import SpeechGender, Story, StoryOrigin
from .contract import WriterError


class StaticStoryWriter:
    def __init__(self, stories: dict[str, Story]) -> None:
        self._stories = stories

    async def write(
        self,
        origin: StoryOrigin,
        *,
        language: Language,
        speech_gender: Optional[SpeechGender] = None,
    ) -> Story:
        if origin.url not in self._stories:
            raise WriterError(f"No story written for {origin.url}")
        story = self._stories[origin.url]
        if speech_gender is not None:
            story = dataclasses.replace(story, resolved_gender=speech_gender)
        return story
