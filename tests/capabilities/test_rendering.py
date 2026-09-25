"""Rendering: any story, any footage source, one video per part, no network."""

import json

import pytest

from src.capabilities.rendering import (
    NarrationOverFootageRenderer,
    select_renderer,
)
from src.capabilities.rendering.captions import CaptionsService
from src.capabilities.rendering.censor import TextCensor
from src.capabilities.rendering.cover import CoverService
from src.capabilities.rendering.cta import compute_cta_start
from src.capabilities.rendering.speech import SpeechService
from src.entities.configs.services.captions import CaptionsConfig
from src.entities.configs.services.video import VideoConfig
from src.entities.language import Language
from src.entities.story import Story, StoryOrigin, StoryPart
from src.entities.transcription import TranscriptionResult, TranscriptionWord
from tests.fakes.proxies import (
    FAKE_TRANSCRIPT,
    FakeCoverProxy,
    FakeLLMProxy,
    FakeSpeechProxy,
    FakeTranscriptionProxy,
    _fixture_bytes,
)
from tests.fakes.video import FAKE_VIDEO_BYTES, FakeComposer, FakeFootageSource

ORIGIN = StoryOrigin(
    url="https://www.reddit.com/r/contos/comments/abc/t/",
    title="t",
    content="c",
    community="r/contos",
    author="u/autor",
    community_image_url="https://example.com/contos.png",
)


def _story(title: str, *texts: str) -> Story:
    return Story(
        title=title,
        parts=[StoryPart(index=i, text=text) for i, text in enumerate(texts, 1)],
        narrator_gender="female",
        resolved_gender="female",
        language=Language.PORTUGUESE,
        summary="",
        origin=ORIGIN,
    )


class _Rig:
    def __init__(self, transcription=None, footage=None):
        self.speech = FakeSpeechProxy()
        self.cover = FakeCoverProxy()
        self.footage = footage or FakeFootageSource()
        self.composer = FakeComposer()
        self.renderer = NarrationOverFootageRenderer(
            speech=SpeechService(self.speech),
            captions=CaptionsService(
                llm_proxy=FakeLLMProxy(),
                transcription_proxy=transcription or FakeTranscriptionProxy(),
                captions_config=CaptionsConfig(),
            ),
            cover=CoverService(self.cover),
            footage=self.footage,
            composer=self.composer,
            censor=TextCensor(),
            video_config=VideoConfig(),
        )


class _SayingTranscription:
    """Transcribes any audio into the given words, one per 0.1 s."""

    def __init__(self, text: str):
        self._words = text.split()

    def transcribe(self, audio_bytes, language=None):
        return TranscriptionResult(
            text=" ".join(self._words),
            words=[
                TranscriptionWord(word=w, start=i / 10, end=(i + 1) / 10)
                for i, w in enumerate(self._words)
            ],
        )


class _FailingOnSecondCompile(FakeFootageSource):
    async def compile(self, *, min_duration, low_quality=False):
        if self.compilations:
            raise RuntimeError("footage exhausted")
        return await super().compile(min_duration=min_duration, low_quality=low_quality)


async def test_one_part_renders_every_artifact():
    rig = _Rig()

    (part,) = await rig.renderer.render(
        _story("A vizinha e o bolo", "Era uma vez."), low_quality=True
    )

    assert part.part.index == 1
    assert part.video == FAKE_VIDEO_BYTES
    assert part.audio == _fixture_bytes("silence_1s.mp3")
    assert part.cover_png == _fixture_bytes("cover.png")
    assert part.cover_title == "A vizinha e o bolo"
    assert rig.cover.titles == ["A vizinha e o bolo"]
    assert [w["word"] for w in json.loads(part.captions_json)] == (
        FAKE_TRANSCRIPT.split()
    )
    assert rig.speech.texts == ["Era uma vez."]

    (composition,) = rig.composer.compositions
    # "curta" is the 6th word of the fake transcript, 0.1 s per word.
    assert composition.cta_start == 0.5
    assert composition.low_quality is True
    # The footage covers the narration it was asked for.
    assert rig.footage.compilations == [pytest.approx(composition.audio_duration)]


async def test_three_parts():
    """Three parts render three videos, each with its part on the cover (SC-004)."""
    rig = _Rig()

    parts = await rig.renderer.render(
        _story("O síndico e a garagem", "Parte um.", "Parte dois.", "Parte três.")
    )

    assert [p.part.index for p in parts] == [1, 2, 3]
    assert [p.cover_title for p in parts] == [
        "O síndico e a garagem - Parte 1",
        "O síndico e a garagem - Parte 2",
        "O síndico e a garagem - Parte 3",
    ]
    assert rig.cover.titles == [p.cover_title for p in parts]
    assert rig.speech.texts == ["Parte um.", "Parte dois.", "Parte três."]
    assert len(rig.footage.compilations) == 3
    assert len(rig.composer.compositions) == 3


async def test_cover_title_and_captions_are_censored():
    rig = _Rig(transcription=_SayingTranscription("ele quis matar o gato"))

    (part,) = await rig.renderer.render(
        _story("Ele quis matar o gato", "Ele quis matar o gato.")
    )

    assert "matar" not in part.cover_title
    assert rig.cover.titles == [part.cover_title]
    captions = [w["word"] for w in json.loads(part.captions_json)]
    assert "matar" not in captions and len(captions) == 5
    (composition,) = rig.composer.compositions
    assert composition.captions == captions


async def test_a_failing_part_fails_the_whole_render():
    rig = _Rig(footage=_FailingOnSecondCompile())

    with pytest.raises(RuntimeError, match="footage exhausted"):
        await rig.renderer.render(_story("Título", "Um.", "Dois."))


def _words(*words: str) -> list[dict]:
    return [
        {"word": w, "start": float(i), "end": float(i + 1)} for i, w in enumerate(words)
    ]


def test_cta_starts_at_the_marker_word():
    words = _words(*["palavra"] * 30, "Curta!", "e", "siga", "a", "página")
    assert compute_cta_start(words) == 30.0


def test_cta_falls_back_to_the_third_to_last_word():
    assert compute_cta_start(_words("um", "dois", "três", "quatro", "cinco")) == 2.0


def test_cta_ignores_a_marker_before_the_last_twenty_words():
    words = _words("curta", *["palavra"] * 25)
    assert compute_cta_start(words) == 23.0


def test_cta_of_an_empty_transcript_is_zero():
    assert compute_cta_start([]) == 0.0


def test_unknown_strategy_names_itself_and_the_available_ones():
    renderers = {"narration-over-footage": _Rig().renderer}

    with pytest.raises(KeyError, match="animation.*narration-over-footage"):
        select_renderer("animation", renderers)


def test_known_strategy_is_selected():
    renderer = _Rig().renderer

    assert (
        select_renderer("narration-over-footage", {renderer.name: renderer}) is renderer
    )
