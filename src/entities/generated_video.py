"""A rendered video waiting to be published, as its manifest records it."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class GeneratedVideo:
    video_path: str
    # The TikTok description: the story title, with the part suffix when
    # the story has more than one part.
    title: str
    summary: str
    post_url: str
    # Every video the daily run produces is "auto"; the field stays in the
    # manifest so the files keep the shape they have always had.
    source: str = "auto"
    # Which part of a multi-part story this is; None for a one-part story.
    part: Optional[int] = None
