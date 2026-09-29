from dataclasses import dataclass, field
from typing import Optional

from src.entities.reddit_post import RedditPost


@dataclass
class StoryCandidate:
    """A Reddit post scored by deterministic metrics before LLM evaluation."""

    post: RedditPost
    deterministic_score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)


# The model's verdicts that make a story worth producing for the base.
BASE_VERDICTS = ("Excelente", "Boa")


@dataclass(frozen=True)
class ExplorationFit:
    """How fair a test of an open experiment a story is: the experiment it
    tests best, None when it tests none, and how well, from 0 to 100."""

    experiment: Optional[str]
    fit: float
    reason: str = ""


@dataclass
class EvaluatedStory:
    """A fully evaluated story with both deterministic and LLM scores."""

    post: RedditPost
    deterministic_score: float = 0.0
    evaluation: dict = field(default_factory=dict)
    # Given only while an experiment is open.
    exploration: Optional[ExplorationFit] = None
    # What the video is made for: "base", or the experiment whose slot it takes.
    goal: str = "base"

    @property
    def nota_geral(self) -> float:
        return self.evaluation.get("nota_geral", 0.0)

    @property
    def veredito(self) -> str:
        return self.evaluation.get("veredito", "")

    @property
    def resumo(self) -> str:
        return self.evaluation.get("resumo", "")

    @property
    def base_worthy(self) -> bool:
        return self.veredito in BASE_VERDICTS
