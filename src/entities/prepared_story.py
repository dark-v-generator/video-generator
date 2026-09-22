"""The story package prepared on the laptop and consumed by the server.

This is the only artifact that travels between the two halves of the flow. It
serializes the exact point of the pipeline after which no LLM call is left
(``PreparedStory``), plus the metadata the publisher needs.
"""

import re
from datetime import datetime
from typing import TYPE_CHECKING, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from src.entities.language import Language
from src.entities.reddit_post import RedditPost

if TYPE_CHECKING:  # pragma: no cover - import kept out of the runtime path
    from src.services.reddit_video_service import PreparedStory

_POST_ID_PATTERN = re.compile(r"/comments/([A-Za-z0-9]+)")


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


class PreparedStoryPackage(BaseModel):
    """A story already written and approved locally, ready to be produced."""

    # Extra keys are ignored on purpose: the assistant may annotate a package
    # (notes, working scores) without the server having to know about it.
    model_config = ConfigDict(extra="ignore")

    version: Literal[1] = Field(title="Package schema version")
    source: str = Field("claude-code", title="Who produced the package")
    language: Language = Field(title="Language the script was written in")
    created_at: datetime = Field(title="When the package was written")
    post: RedditPost = Field(title="The original Reddit post")
    story_title: str = Field(title="Cover title, used verbatim")
    script_text: str = Field(title="Narration script, used verbatim")
    narrator_gender: Literal["male", "female", "unknown"]
    resolved_gender: Literal["male", "female"] = Field(title="Voice to narrate with")
    summary: str = Field(title="3-5 sentence summary for the manifest and hashtags")
    hashtags: Optional[List[str]] = Field(
        None, title="Hashtags without '#'; when present the server skips the LLM"
    )

    @field_validator("story_title", "script_text", "summary")
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

    def to_prepared_story(self) -> "PreparedStory":
        # Imported here because reddit_video_service pulls in the whole video
        # editing stack, which the local CLI has no reason to load.
        from src.services.reddit_video_service import PreparedStory

        return PreparedStory(
            post=self.post,
            script_text=self.script_text,
            story_title=self.story_title,
            narrator_gender=self.narrator_gender,
            resolved_gender=self.resolved_gender,
            original_post_md=self.original_post_md,
        )
