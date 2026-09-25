"""A story told over one or more videos, and the text it was adapted from."""

from dataclasses import dataclass
from typing import Literal, Optional

from .language import Language
from .reddit_post import RedditPost

NarratorGender = Literal["male", "female", "unknown"]
SpeechGender = Literal["male", "female"]

_PART_WORDS = {
    Language.PORTUGUESE: "Parte",
    Language.SPANISH: "Parte",
    Language.ITALIAN: "Parte",
    Language.FRENCH: "Partie",
    Language.GERMAN: "Teil",
}


def _part_word(language: Language) -> str:
    return _PART_WORDS.get(language, "Part")


def part_label(language: Language, index: int) -> str:
    """Suffix that tells the viewer which part of a multi-part story this is."""
    return f" - {_part_word(language)} {index}"


@dataclass(frozen=True)
class StoryOrigin:
    """The source text of a story and the attribution its cover shows."""

    url: str
    title: str
    content: str
    community: str
    author: str
    community_image_url: str

    @classmethod
    def from_post(cls, post: RedditPost) -> "StoryOrigin":
        return cls(
            url=post.url or "",
            title=post.title,
            content=post.content,
            community=post.community,
            author=post.author,
            community_image_url=post.community_url_photo,
        )

    @property
    def original_markdown(self) -> str:
        return f"# {self.title}\n\n{self.content}\n"


@dataclass(frozen=True)
class StoryPart:
    index: int
    text: str


@dataclass(frozen=True)
class Story:
    """A written story, ready to be narrated as one video per part."""

    title: str
    parts: list[StoryPart]
    narrator_gender: NarratorGender
    resolved_gender: SpeechGender
    language: Language
    summary: str
    origin: StoryOrigin
    hashtags: Optional[list[str]] = None

    def __post_init__(self) -> None:
        if not self.parts:
            raise ValueError("A story needs at least one part")
        indexes = [part.index for part in self.parts]
        if indexes != list(range(1, len(self.parts) + 1)):
            raise ValueError(f"Part indexes must be 1..{len(self.parts)}: {indexes}")
        empty = [part.index for part in self.parts if not part.text.strip()]
        if empty:
            raise ValueError(f"Story parts without text: {empty}")

    @property
    def is_multipart(self) -> bool:
        return len(self.parts) > 1

    def cover_title_for(self, part: StoryPart) -> str:
        if not self.is_multipart:
            return self.title
        return f"{self.title}{part_label(self.language, part.index)}"

    @property
    def story_markdown(self) -> str:
        markdown = f"# {self.title}\n\n"
        markdown += (
            f"**Narrator gender:** {self.narrator_gender} "
            f"→ resolved: {self.resolved_gender}\n\n"
        )
        if not self.is_multipart:
            return markdown + f"{self.parts[0].text}\n"
        word = _part_word(self.language)
        return markdown + "\n".join(
            f"## {word} {part.index}\n\n{part.text}\n" for part in self.parts
        )
