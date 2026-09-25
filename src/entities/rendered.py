"""What rendering one part of a story produces."""

from dataclasses import dataclass
from typing import Optional

from .story import StoryPart


@dataclass(frozen=True)
class RenderedPart:
    """The artifacts of one rendered part, ready to be written or published."""

    part: StoryPart
    # The title as the cover shows it: with the part suffix, censored.
    cover_title: str
    video: bytes
    audio: bytes
    # JSON list of censored {word, start, end} dicts.
    captions_json: str
    cover_png: Optional[bytes]
