"""The story package prepared on the laptop and consumed by the server.

This is the only artifact that travels between the two halves of the flow. It
serializes the exact point of the pipeline after which no LLM call is left
(``PreparedStory``), plus the metadata the publisher needs.

Two shapes share the same file name and identity: version 1 is a story told in
one video, version 2 in two. ``version`` is what picks the model, which is also
what makes a server that predates two-part support reject a version 2 package
instead of half-producing it.
"""

import json
import re
from datetime import datetime
from typing import TYPE_CHECKING, List, Literal, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from src.entities.language import Language
from src.entities.reddit_post import RedditPost

if TYPE_CHECKING:  # pragma: no cover - import kept out of the runtime path
    from src.services.reddit_video_service import PreparedStory, StoryScript

_POST_ID_PATTERN = re.compile(r"/comments/([A-Za-z0-9]+)")

PART_SUFFIXES = (" - Parte 1", " - Parte 2")


def extract_post_id(url: Optional[str]) -> str:
    """Return the Reddit post id a permalink carries.

    The id names the package file, which is what makes a duplicate detectable
    on the server with a single ``test -e``.
    """
    match = _POST_ID_PATTERN.search(url or "")
    if not match:
        raise ValueError(
            f"Não foi possível extrair o id do post da URL {url!r}. "
            "Esperado um permalink com /comments/<id>/."
        )
    return match.group(1)


class _PackageBase(BaseModel):
    """Everything the two package shapes have in common."""

    # Extra keys are ignored on purpose: the assistant may annotate a package
    # (notes, working scores) without the server having to know about it.
    model_config = ConfigDict(extra="ignore")

    source: str = Field("claude-code", title="Who produced the package")
    language: Language = Field(title="Language the script was written in")
    created_at: datetime = Field(title="When the package was written")
    post: RedditPost = Field(title="The original Reddit post")
    story_title: str = Field(title="Cover title, used verbatim")
    narrator_gender: Literal["male", "female", "unknown"]
    resolved_gender: Literal["male", "female"] = Field(title="Voice to narrate with")
    summary: str = Field(title="3-5 sentence summary for the manifest and hashtags")
    hashtags: Optional[List[str]] = Field(
        None, title="Hashtags without '#'; when present the server skips the LLM"
    )

    # The script fields live on the subclasses, so the shared validator has to
    # be told not to check that every name exists on this base.
    @field_validator(
        "story_title",
        "summary",
        "script_text",
        "part1_text",
        "part2_text",
        check_fields=False,
    )
    @classmethod
    def _reject_blank(cls, value: str, info: ValidationInfo) -> str:
        if not value.strip():
            raise ValueError(f"{info.field_name} não pode ser vazio")
        return value

    @field_validator("post")
    @classmethod
    def _require_extractable_post_id(cls, post: RedditPost) -> RedditPost:
        extract_post_id(post.url)
        return post

    @property
    def post_id(self) -> str:
        return extract_post_id(self.post.url)

    @property
    def original_post_md(self) -> str:
        """Same markdown ``prepare_satisfying_story`` builds from the post."""
        return f"# {self.post.title}\n\n{self.post.content}\n"

    def _prepared_story(self, script_text: str, title: str) -> "PreparedStory":
        # Imported here because reddit_video_service pulls in the whole video
        # editing stack, which the local CLI has no reason to load.
        from src.services.reddit_video_service import PreparedStory

        return PreparedStory(
            post=self.post,
            script_text=script_text,
            story_title=title,
            narrator_gender=self.narrator_gender,
            resolved_gender=self.resolved_gender,
            original_post_md=self.original_post_md,
        )


class PreparedStoryPackage(_PackageBase):
    """A story already written and approved locally, ready to be produced."""

    version: Literal[1] = Field(title="Package schema version")
    script_text: str = Field(title="Narration script, used verbatim")

    def to_prepared_story(self) -> "PreparedStory":
        return self._prepared_story(self.script_text, self.story_title)


class TwoPartStoryPackage(_PackageBase):
    """The same story cut in two videos, published in consecutive slots."""

    version: Literal[2] = Field(title="Package schema version")
    part1_text: str = Field(title="Part 1 narration, ending on the part-2 invite")
    part2_text: str = Field(title="Part 2 narration, with the climax and the close")

    def to_story_script(self) -> "StoryScript":
        from src.services.reddit_video_service import StoryScript

        return StoryScript(
            title=self.story_title,
            part1=self.part1_text,
            part2=self.part2_text,
            narrator_gender=self.narrator_gender,
            resolved_gender=self.resolved_gender,
        )

    def to_prepared_stories(self) -> Tuple["PreparedStory", "PreparedStory"]:
        """One prepared story per part, each with its own cover title.

        The suffix lives here and not in the package so the operator writes
        (and hears) a single title, while each video still tells the viewer
        which half they are watching.
        """
        first, second = PART_SUFFIXES
        return (
            self._prepared_story(self.part1_text, f"{self.story_title}{first}"),
            self._prepared_story(self.part2_text, f"{self.story_title}{second}"),
        )


StoryPackage = Union[PreparedStoryPackage, TwoPartStoryPackage]

_PACKAGE_MODELS = {1: PreparedStoryPackage, 2: TwoPartStoryPackage}


def load_package(text: str) -> StoryPackage:
    """Read a package file, choosing the model by its ``version``.

    Everything that reads a package — CLI, queue, bot — goes through here, so
    an unknown version fails in one place with one message instead of being
    silently coerced into the shape the reader happened to expect.
    """
    data = json.loads(text)
    model = _PACKAGE_MODELS.get(data.get("version")) if isinstance(data, dict) else None
    if model is None:
        raise ValueError("unsupported package version")
    return model.model_validate(data)
