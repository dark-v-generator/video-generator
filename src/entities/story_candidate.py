from dataclasses import dataclass, field
from typing import Optional

from src.entities.reddit_post import RedditPost


@dataclass
class StoryCandidate:
    """A Reddit post scored by deterministic metrics before LLM evaluation."""

    post: RedditPost
    deterministic_score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)


@dataclass
class EvaluatedStory:
    """A fully evaluated story with both deterministic and LLM scores."""

    post: RedditPost
    deterministic_score: float = 0.0
    evaluation: dict = field(default_factory=dict)

    @property
    def nota_geral(self) -> float:
        return self.evaluation.get("nota_geral", 0.0)

    @property
    def veredito(self) -> str:
        return self.evaluation.get("veredito", "")

    @property
    def resumo(self) -> str:
        return self.evaluation.get("resumo", "")
