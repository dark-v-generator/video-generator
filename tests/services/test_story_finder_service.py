import pytest

from src.entities.config import EvaluationConfig
from src.services.story_finder_service import StoryFinderService


class FailingRedditProxy:
    def list_subreddit_posts(self, *, subreddit, **kwargs):
        raise RuntimeError(f"blocked {subreddit}")


class UnusedLLMProxy:
    pass


@pytest.mark.asyncio
async def test_find_best_stories_raises_when_all_subreddits_fail():
    service = StoryFinderService(
        reddit_proxy=FailingRedditProxy(),
        llm_proxy=UnusedLLMProxy(),
        evaluation_config=EvaluationConfig(
            subreddits=["pettyrevenge", "relacionamentos"],
        ),
    )

    with pytest.raises(RuntimeError) as exc:
        await service.find_best_stories()

    assert "nenhum subreddit" in str(exc.value)
    assert "r/pettyrevenge" in str(exc.value)
    assert "r/relacionamentos" in str(exc.value)
