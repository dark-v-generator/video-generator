"""What any story discovery promises: ranked candidates, grades, origins and
the post's current numbers."""

from typing import Literal, Optional, Protocol, Sequence

from ...entities.history import RedditSnapshot
from ...entities.language import Language
from ...entities.story import StoryOrigin
from ...entities.story_candidate import EvaluatedStory, StoryCandidate
from ...entities.tuning import Experiment

Sort = Literal["top", "new", "hot"]
TimeFilter = Literal["hour", "day", "week", "month", "year", "all"]


class StoryDiscovery(Protocol):
    def fetch(self, url: str) -> StoryOrigin: ...

    def signals(self, url: str) -> RedditSnapshot:
        """The post's numbers now, as a collection snapshot; a post that is
        gone is ``available=False``. Any other failure raises."""
        ...

    async def find_candidates(
        self,
        *,
        sort: Sort = "top",
        time_filter: TimeFilter = "day",
        posts_per_sub: int = 25,
        top_per_sub: int = 5,
        subreddits: Optional[list[str]] = None,
        exclude_urls: Optional[set[str]] = None,
    ) -> list[StoryCandidate]: ...

    async def grade(
        self, candidates: list[StoryCandidate], language: Language
    ) -> list[EvaluatedStory]: ...

    async def find_best_stories(
        self,
        *,
        language: Language,
        sort: Sort = "top",
        time_filter: TimeFilter = "day",
        posts_per_sub: int = 25,
        top_per_sub: int = 5,
        subreddits: Optional[list[str]] = None,
        exclude_urls: Optional[set[str]] = None,
        experiments: Sequence[Experiment] = (),
        min_fit: int = 70,
    ) -> list[EvaluatedStory]:
        """The day's base stories: the graded "Excelente" and "Boa", best
        first. With *experiments*, every graded story also gets the
        exploration grade, and the ones that reach *min_fit* and are not
        already listed follow, best fit first. A failed exploration grade
        raises."""
        ...
