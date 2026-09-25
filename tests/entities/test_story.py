import pytest

from src.entities.language import Language
from src.entities.reddit_post import RedditPost
from src.entities.story import Story, StoryOrigin, StoryPart, part_label

ORIGIN = StoryOrigin(
    url="https://www.reddit.com/r/x/comments/abc/t/",
    title="Original",
    content="Body",
    community="r/x",
    author="u/y",
    community_image_url="https://example.com/x.png",
)


def story(*texts: str, language: Language = Language.PORTUGUESE) -> Story:
    return Story(
        title="Minha sogra",
        parts=[StoryPart(index=i, text=t) for i, t in enumerate(texts, start=1)],
        narrator_gender="female",
        resolved_gender="female",
        language=language,
        summary="",
        origin=ORIGIN,
    )


class TestCoverTitle:
    def test_single_part_has_no_suffix(self):
        single = story("Tudo numa parte.")

        assert not single.is_multipart
        assert single.cover_title_for(single.parts[0]) == "Minha sogra"

    def test_each_of_three_parts_is_numbered(self):
        three = story("Um.", "Dois.", "Três.")

        assert three.is_multipart
        assert [three.cover_title_for(p) for p in three.parts] == [
            "Minha sogra - Parte 1",
            "Minha sogra - Parte 2",
            "Minha sogra - Parte 3",
        ]


class TestPartLabel:
    def test_portuguese(self):
        assert part_label(Language("pt-br"), 2) == " - Parte 2"

    def test_english(self):
        assert part_label(Language.ENGLISH, 3) == " - Part 3"


class TestOrigin:
    def test_from_post_keeps_the_attribution(self):
        post = RedditPost(
            title="T",
            content="C",
            community="r/sub",
            author="u/me",
            community_url_photo="https://example.com/sub.png",
            url="https://www.reddit.com/r/sub/comments/1/",
        )

        origin = StoryOrigin.from_post(post)

        assert origin == StoryOrigin(
            url="https://www.reddit.com/r/sub/comments/1/",
            title="T",
            content="C",
            community="r/sub",
            author="u/me",
            community_image_url="https://example.com/sub.png",
        )
        assert origin.original_markdown == "# T\n\nC\n"


class TestValidation:
    def test_no_parts(self):
        with pytest.raises(ValueError, match="at least one part"):
            story()

    def test_empty_part(self):
        with pytest.raises(ValueError, match=r"without text: \[2\]"):
            story("Um.", "  ")

    def test_indexes_out_of_order(self):
        with pytest.raises(ValueError, match="1..2"):
            Story(
                title="T",
                parts=[StoryPart(index=2, text="a"), StoryPart(index=1, text="b")],
                narrator_gender="unknown",
                resolved_gender="male",
                language=Language.PORTUGUESE,
                summary="",
                origin=ORIGIN,
            )


class TestMarkdown:
    def test_single_part_matches_the_old_story_md(self):
        assert story("Texto.").story_markdown == (
            "# Minha sogra\n\n"
            "**Narrator gender:** female → resolved: female\n\n"
            "Texto.\n"
        )

    def test_parts_get_their_own_heading(self):
        markdown = story("Um.", "Dois.").story_markdown

        assert "## Parte 1\n\nUm.\n" in markdown
        assert "## Parte 2\n\nDois.\n" in markdown
