"""Fake renderer: one fixed video per part, no speech, captions or footage."""

from typing import List

from src.entities.rendered import RenderedPart
from src.entities.story import Story


class EchoRenderer:
    name = "echo"

    def __init__(self):
        self.stories: List[Story] = []

    async def render(
        self, story: Story, *, low_quality: bool = False
    ) -> list[RenderedPart]:
        self.stories.append(story)
        return [
            RenderedPart(
                part=part,
                cover_title=story.cover_title_for(part),
                video=b"video",
                audio=b"audio",
                captions_json="[]",
                cover_png=None,
            )
            for part in story.parts
        ]
