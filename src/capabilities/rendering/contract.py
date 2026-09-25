"""What a rendering strategy promises: a story in, one rendered video per part out."""

from typing import Protocol

from ...entities.rendered import RenderedPart
from ...entities.story import Story


class Renderer(Protocol):
    """Turns every part of a story into a video.

    A part that fails raises; the renderer never writes nor publishes anything,
    so the caller decides what a partial failure means.
    """

    name: str

    async def render(
        self, story: Story, *, low_quality: bool = False
    ) -> list[RenderedPart]: ...
