"""Fake proxies with fixed answers and a programmable error sequence."""

import os
from typing import Dict, List, Literal, Optional

from src.entities.language import Language
from src.entities.reddit_post import RedditPost
from src.entities.speech_voice import SpeechVoice
from src.entities.transcription import TranscriptionResult, TranscriptionWord
from src.proxies.interfaces import (
    ICoverProxy,
    ILLMProxy,
    IRedditProxy,
    ISpeechProxy,
    ITranscriptionProxy,
)

_FIXTURES = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures")


def _fixture_bytes(name: str) -> bytes:
    with open(os.path.join(_FIXTURES, name), "rb") as f:
        return f.read()


class FakeRedditProxy(IRedditProxy):
    """Serves a fixed set of posts per subreddit and by URL."""

    def __init__(self, posts_by_subreddit: Dict[str, List[RedditPost]]):
        self._posts_by_subreddit = posts_by_subreddit
        self.listed: List[str] = []
        self.fetched: List[str] = []

    def get_reddit_post(self, url: str) -> RedditPost:
        self.fetched.append(url)
        for posts in self._posts_by_subreddit.values():
            for post in posts:
                if post.url == url:
                    return post
        raise KeyError(f"No fake post for {url}")

    def list_subreddit_posts(
        self,
        subreddit: str,
        sort: Literal["top", "new", "hot"] = "top",
        time_filter: Literal["hour", "day", "week", "month", "year", "all"] = "day",
        limit: int = 25,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> List[RedditPost]:
        self.listed.append(subreddit)
        return list(self._posts_by_subreddit.get(subreddit, []))[:limit]


class FakeLLMProxy(ILLMProxy):
    """Answers every prompt deterministically from the post title.

    ``grades`` sets each post's overall grade, which is what orders discovery.
    ``story_errors`` maps a post title to the exceptions ``generate_story``
    raises, one per call, before it starts answering normally.
    """

    def __init__(
        self,
        grades: Optional[Dict[str, float]] = None,
        story_errors: Optional[Dict[str, List[Exception]]] = None,
    ):
        self._grades = grades or {}
        self._story_errors = {k: list(v) for k, v in (story_errors or {}).items()}
        self.calls: List[tuple[str, str]] = []

    async def generate_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        self.calls.append(("generate_story", title))
        errors = self._story_errors.get(title)
        if errors:
            raise errors.pop(0)
        return {
            "title": f"Roteiro: {title}",
            "narrator_gender": "female",
            "script": f"{title}. {content} Curta e siga para a parte dois.",
        }

    async def evaluate_story(
        self, title: str, content: str, target_language: Language
    ) -> dict:
        self.calls.append(("evaluate_story", title))
        grade = self._grades.get(title, 70.0)
        return {
            "resumo": f"Resumo de {title}",
            "notas": {},
            "nota_geral": grade,
            "veredito": "Excelente" if grade >= 85 else "Boa",
        }

    async def generate_hashtags(
        self, title: str, summary: str, target_language: Language
    ) -> List[str]:
        self.calls.append(("generate_hashtags", title))
        return ["historia", "reddit"]

    async def enhance_transcription(
        self, base_text: str, raw_transcription: List[dict]
    ) -> List[dict]:
        self.calls.append(("enhance_transcription", base_text[:40]))
        return raw_transcription


class FakeSpeechProxy(ISpeechProxy):
    """Returns one second of real, decodable silence for any text."""

    def __init__(self):
        self.texts: List[str] = []

    async def generate_speech(
        self,
        text: str,
        gender: Literal["male", "female"] = "male",
        rate: float = 1.0,
        language: Language = Language.PORTUGUESE,
        override_voice_id: Optional[str] = None,
    ) -> bytes:
        self.texts.append(text)
        return _fixture_bytes("silence_1s.mp3")

    def list_voices(self) -> List[SpeechVoice]:
        return []


FAKE_TRANSCRIPT = "era uma vez uma historia curta e siga"


class FakeTranscriptionProxy(ITranscriptionProxy):
    """Transcribes any audio into the same short sentence, one word per 0.1 s."""

    def transcribe(
        self, audio_bytes: bytes, language: Optional[Language] = None
    ) -> TranscriptionResult:
        words = [
            TranscriptionWord(
                word=word, start=round(i * 0.1, 2), end=round((i + 1) * 0.1, 2)
            )
            for i, word in enumerate(FAKE_TRANSCRIPT.split())
        ]
        return TranscriptionResult(text=FAKE_TRANSCRIPT, words=words)


class FakeCoverProxy(ICoverProxy):
    """Returns a small real PNG and remembers the titles it was asked for."""

    def __init__(self):
        self.titles: List[str] = []

    async def create_reddit_cover(
        self,
        title: str,
        community: str,
        author: str,
        community_url_photo: str,
    ) -> bytes:
        self.titles.append(title)
        return _fixture_bytes("cover.png")
