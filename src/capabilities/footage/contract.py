"""What any footage source promises: a background clip at least as long as asked."""

from dataclasses import dataclass, field
from typing import Protocol

from ...entities.editor.video_clip import VideoClip


@dataclass
class Footage:
    clip: VideoClip  # already anti-fingerprinted, clip by clip
    sources: list[str] = field(default_factory=list)  # ids / file names, in order


class FootageShortfallError(Exception):
    """Every usable clip was used and the footage is still too short."""

    def __init__(self, needed: float, got: float, detail: str = ""):
        self.needed = needed
        self.got = got
        message = (
            f"Footage covers {got:.1f}s of the {needed:.1f}s needed "
            f"(short by {needed - got:.1f}s)"
        )
        super().__init__(f"{message}: {detail}" if detail else message)


class FootageSource(Protocol):
    async def compile(
        self, *, min_duration: float, low_quality: bool = False
    ) -> Footage: ...
