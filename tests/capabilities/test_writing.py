import litellm
import pytest

from src.capabilities.writing import (
    ModelStoryWriter,
    StaticStoryWriter,
    WriterContentBlockedError,
    WriterError,
    WriterTransientError,
)
from src.entities.language import Language
from src.entities.story import Story, StoryOrigin, StoryPart
from tests.fakes.proxies import FakeLLMProxy

ORIGIN = StoryOrigin(
    url="https://www.reddit.com/r/x/comments/abc/t/",
    title="A vizinha e o bolo",
    content="Ela roubou meu bolo.",
    community="r/x",
    author="u/y",
    community_image_url="https://example.com/x.png",
)


class _AnsweringLLM(FakeLLMProxy):
    def __init__(self, answer: dict):
        super().__init__()
        self._answer = answer

    async def generate_story(self, title, content, target_language):
        self.calls.append(("generate_story", title))
        return dict(self._answer)


class TestModelStoryWriter:
    @pytest.mark.asyncio
    async def test_writes_a_one_part_story_from_the_model(self):
        llm = FakeLLMProxy()

        story = await ModelStoryWriter(llm).write(ORIGIN, language=Language.PORTUGUESE)

        assert llm.calls == [("generate_story", "A vizinha e o bolo")]
        assert story.title == "Roteiro: A vizinha e o bolo"
        assert story.parts == [
            StoryPart(
                index=1,
                text="A vizinha e o bolo. Ela roubou meu bolo. "
                "Curta e siga para a parte dois.",
            )
        ]
        assert story.narrator_gender == "female"
        assert story.resolved_gender == "female"
        assert story.language == Language.PORTUGUESE
        assert story.summary == ""
        assert story.origin == ORIGIN
        assert story.hashtags is None

    @pytest.mark.asyncio
    async def test_the_caller_voice_wins_over_the_narrator(self):
        story = await ModelStoryWriter(FakeLLMProxy()).write(
            ORIGIN, language=Language.PORTUGUESE, speech_gender="male"
        )

        assert story.narrator_gender == "female"
        assert story.resolved_gender == "male"

    @pytest.mark.asyncio
    async def test_unknown_narrator_is_voiced_male(self):
        llm = _AnsweringLLM({"title": "T", "narrator_gender": "?", "script": "S"})

        story = await ModelStoryWriter(llm).write(ORIGIN, language=Language.PORTUGUESE)

        assert story.narrator_gender == "unknown"
        assert story.resolved_gender == "male"

    @pytest.mark.asyncio
    async def test_missing_title_falls_back_to_the_origin(self):
        llm = _AnsweringLLM({"script": "S"})

        story = await ModelStoryWriter(llm).write(ORIGIN, language=Language.PORTUGUESE)

        assert story.title == ORIGIN.title
        assert story.narrator_gender == "unknown"


class TestErrorClassification:
    @pytest.mark.parametrize(
        "error, expected",
        [
            (RuntimeError("429 Too Many Requests"), WriterTransientError),
            (RuntimeError("Request timeout"), WriterTransientError),
            (RuntimeError("502 Bad Gateway"), WriterTransientError),
            (
                litellm.RateLimitError("slow down", "openrouter", "m"),
                WriterTransientError,
            ),
            (
                RuntimeError("Response blocked by content filter"),
                WriterContentBlockedError,
            ),
            (RuntimeError("Could not parse valid JSON"), WriterError),
        ],
    )
    @pytest.mark.asyncio
    async def test_model_failures_become_writer_errors(self, error, expected):
        llm = FakeLLMProxy(story_errors={ORIGIN.title: [error]})

        with pytest.raises(WriterError) as raised:
            await ModelStoryWriter(llm).write(ORIGIN, language=Language.PORTUGUESE)

        assert type(raised.value) is expected
        assert str(raised.value) == str(error)
        assert raised.value.__cause__ is error

    @pytest.mark.asyncio
    async def test_a_refusal_is_not_retried_even_with_a_transient_status(self):
        llm = FakeLLMProxy(
            story_errors={ORIGIN.title: [RuntimeError("429: blocked by safety filter")]}
        )

        with pytest.raises(WriterContentBlockedError):
            await ModelStoryWriter(llm).write(ORIGIN, language=Language.PORTUGUESE)


class TestStaticStoryWriter:
    def _story(self) -> Story:
        return Story(
            title="Escrita à mão",
            parts=[StoryPart(index=1, text="Um."), StoryPart(index=2, text="Dois.")],
            narrator_gender="female",
            resolved_gender="female",
            language=Language.PORTUGUESE,
            summary="",
            origin=ORIGIN,
        )

    @pytest.mark.asyncio
    async def test_returns_the_registered_story(self):
        story = self._story()

        written = await StaticStoryWriter({ORIGIN.url: story}).write(
            ORIGIN, language=Language.PORTUGUESE
        )

        assert written is story

    @pytest.mark.asyncio
    async def test_the_caller_voice_wins(self):
        written = await StaticStoryWriter({ORIGIN.url: self._story()}).write(
            ORIGIN, language=Language.PORTUGUESE, speech_gender="male"
        )

        assert written.resolved_gender == "male"

    @pytest.mark.asyncio
    async def test_unknown_origin_fails(self):
        with pytest.raises(WriterError, match="abc"):
            await StaticStoryWriter({}).write(ORIGIN, language=Language.PORTUGUESE)
