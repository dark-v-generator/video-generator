import time

import pytest

from src.capabilities.discovery import RedditStoryDiscovery
from src.entities.config import EvaluationConfig
from src.entities.language import Language
from src.entities.reddit_post import RedditPost
from src.entities.story import StoryOrigin
from src.entities.story_candidate import EvaluatedStory, StoryCandidate


class FailingRedditProxy:
    def list_subreddit_posts(self, *, subreddit, **kwargs):
        raise RuntimeError(f"blocked {subreddit}")


class UnusedLLMProxy:
    pass


@pytest.mark.asyncio
async def test_find_best_stories_raises_when_all_subreddits_fail():
    service = RedditStoryDiscovery(
        reddit=FailingRedditProxy(),
        llm=UnusedLLMProxy(),
        evaluation=EvaluationConfig(
            subreddits=["pettyrevenge", "relacionamentos"],
        ),
    )

    with pytest.raises(RuntimeError) as exc:
        await service.find_best_stories(language=Language.PORTUGUESE)

    assert "nenhum subreddit" in str(exc.value)
    assert "r/pettyrevenge" in str(exc.value)
    assert "r/relacionamentos" in str(exc.value)


class FakeRedditProxy:
    """Serves canned posts per subreddit; a subreddit mapped to an exception fails."""

    def __init__(self, posts_by_sub: dict):
        self._posts_by_sub = posts_by_sub
        self.calls: list[dict] = []

    def list_subreddit_posts(self, *, subreddit, **kwargs):
        self.calls.append({"subreddit": subreddit, **kwargs})
        result = self._posts_by_sub[subreddit]
        if isinstance(result, Exception):
            raise result
        return result


class ForbiddenLLMProxy:
    """The local shortlist must never reach a paid model (SC-002)."""

    async def evaluate_story(self, **kwargs):
        raise AssertionError("evaluate_story must not be called by find_candidates")


def make_post(
    sub: str, post_id: str, score: int, num_comments: int = 120
) -> RedditPost:
    return RedditPost(
        title=f"Story {post_id}",
        content=(
            'I told my boss I would follow the rules. "Every single one", he said.\n\n'
            "So I did exactly that, and my team noticed within a week.\n\n"
            "The client called the next morning. Nobody expected what came next.\n\n"
            "My manager asked me to explain. I showed him the email.\n\n"
            "He went quiet for a long time, and then he laughed."
        )
        * 4,
        community=f"r/{sub}",
        author="u/someone",
        url=f"https://www.reddit.com/r/{sub}/comments/{post_id}/slug/",
        score=score,
        num_comments=num_comments,
        upvote_ratio=0.95,
        created_utc=time.time() - 3600,
    )


def build_service(posts_by_sub: dict, subreddits: list[str]) -> RedditStoryDiscovery:
    return RedditStoryDiscovery(
        reddit=FakeRedditProxy(posts_by_sub),
        llm=ForbiddenLLMProxy(),
        evaluation=EvaluationConfig(subreddits=subreddits),
    )


@pytest.mark.asyncio
async def test_find_candidates_returns_candidates_sorted_by_score():
    service = build_service(
        {
            "pettyrevenge": [
                make_post("pettyrevenge", "aaa", 400),
                make_post("pettyrevenge", "bbb", 9000),
            ],
            "Antiwork": [make_post("Antiwork", "ccc", 3000)],
        },
        ["pettyrevenge", "Antiwork"],
    )

    candidates = await service.find_candidates()

    assert all(isinstance(c, StoryCandidate) for c in candidates)
    scores = [c.deterministic_score for c in candidates]
    assert scores == sorted(scores, reverse=True)
    assert {c.post.title for c in candidates} == {"Story aaa", "Story bbb", "Story ccc"}


@pytest.mark.asyncio
async def test_find_candidates_respects_top_per_sub():
    service = build_service(
        {
            "pettyrevenge": [
                make_post("pettyrevenge", "aaa", 400),
                make_post("pettyrevenge", "bbb", 9000),
                make_post("pettyrevenge", "ccc", 5000),
            ]
        },
        ["pettyrevenge"],
    )

    candidates = await service.find_candidates(top_per_sub=2)

    assert [c.post.title for c in candidates] == ["Story bbb", "Story ccc"]


@pytest.mark.asyncio
async def test_find_candidates_excludes_urls_before_the_per_sub_cut():
    best = make_post("pettyrevenge", "bbb", 9000)
    service = build_service(
        {
            "pettyrevenge": [
                make_post("pettyrevenge", "aaa", 400),
                best,
                make_post("pettyrevenge", "ccc", 5000),
            ]
        },
        ["pettyrevenge"],
    )

    candidates = await service.find_candidates(top_per_sub=1, exclude_urls={best.url})

    assert [c.post.title for c in candidates] == ["Story ccc"]


@pytest.mark.asyncio
async def test_find_candidates_skips_failing_subreddits_and_keeps_the_others():
    service = build_service(
        {
            "pettyrevenge": RuntimeError("blocked"),
            "Antiwork": [make_post("Antiwork", "ccc", 3000)],
        },
        ["pettyrevenge", "Antiwork"],
    )

    candidates = await service.find_candidates()

    assert [c.post.title for c in candidates] == ["Story ccc"]


@pytest.mark.asyncio
async def test_find_candidates_raises_when_every_subreddit_fails():
    service = RedditStoryDiscovery(
        reddit=FailingRedditProxy(),
        llm=ForbiddenLLMProxy(),
        evaluation=EvaluationConfig(subreddits=["pettyrevenge"]),
    )

    with pytest.raises(RuntimeError) as exc:
        await service.find_candidates()

    assert "nenhum subreddit" in str(exc.value)


@pytest.mark.asyncio
async def test_find_candidates_forwards_the_fetch_parameters():
    proxy = FakeRedditProxy({"Antiwork": [make_post("Antiwork", "ccc", 3000)]})
    service = RedditStoryDiscovery(
        reddit=proxy,
        llm=ForbiddenLLMProxy(),
        evaluation=EvaluationConfig(
            subreddits=["pettyrevenge"], min_chars=500, max_chars=15000
        ),
    )

    await service.find_candidates(
        sort="hot", time_filter="week", posts_per_sub=7, subreddits=["Antiwork"]
    )

    assert proxy.calls == [
        {
            "subreddit": "Antiwork",
            "sort": "hot",
            "time_filter": "week",
            "limit": 7,
            "min_chars": 500,
            "max_chars": 15000,
        }
    ]


class RecordingLLMProxy:
    def __init__(self):
        self.evaluated: list[str] = []

    async def evaluate_story(self, *, title, content, target_language):
        self.evaluated.append(title)
        return {
            "nota_geral": 85.0,
            "veredito": "Excelente",
            "resumo": "resumo",
            "notas": {},
        }


@pytest.mark.asyncio
async def test_find_best_stories_still_evaluates_the_candidates():
    llm = RecordingLLMProxy()
    service = RedditStoryDiscovery(
        reddit=FakeRedditProxy(
            {
                "pettyrevenge": [
                    make_post("pettyrevenge", "aaa", 400),
                    make_post("pettyrevenge", "bbb", 9000),
                ]
            }
        ),
        llm=llm,
        evaluation=EvaluationConfig(subreddits=["pettyrevenge"]),
    )

    result = await service.find_best_stories(language=Language.PORTUGUESE)

    assert sorted(llm.evaluated) == ["Story aaa", "Story bbb"]
    assert [story.veredito for story in result] == ["Excelente", "Excelente"]
    assert all(isinstance(story, EvaluatedStory) for story in result)


class FailingLLMProxy:
    async def evaluate_story(self, *, title, content, target_language):
        if title == "Story aaa":
            raise RuntimeError("model down")
        return {
            "nota_geral": 70.0,
            "veredito": "Boa",
            "resumo": "resumo",
            "notas": {},
        }


@pytest.mark.asyncio
async def test_grade_turns_a_failed_evaluation_into_a_zero_instead_of_raising():
    service = RedditStoryDiscovery(
        reddit=FakeRedditProxy({}),
        llm=FailingLLMProxy(),
        evaluation=EvaluationConfig(subreddits=["pettyrevenge"]),
    )
    candidates = [
        StoryCandidate(post=make_post("pettyrevenge", "aaa", 400)),
        StoryCandidate(post=make_post("pettyrevenge", "bbb", 9000)),
    ]

    graded = await service.grade(candidates, Language.PORTUGUESE)

    assert [(g.post.title, g.veredito, g.nota_geral) for g in graded] == [
        ("Story bbb", "Boa", 70.0),
        ("Story aaa", "Erro", 0.0),
    ]


class SinglePostRedditProxy:
    def __init__(self, post: RedditPost):
        self._post = post
        self.urls: list[str] = []

    def get_reddit_post(self, url):
        self.urls.append(url)
        return self._post


def test_fetch_reads_the_post_as_a_story_origin():
    post = make_post("pettyrevenge", "aaa", 400)
    proxy = SinglePostRedditProxy(post)
    service = RedditStoryDiscovery(
        reddit=proxy,
        llm=ForbiddenLLMProxy(),
        evaluation=EvaluationConfig(subreddits=["pettyrevenge"]),
    )

    origin = service.fetch(post.url)

    assert proxy.urls == [post.url]
    assert origin == StoryOrigin.from_post(post)
