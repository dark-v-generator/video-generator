"""The share of the daily production kept to learn: which experiments are open
and what the run makes for them."""

from .allocation import arrange, slots_due
from .contract import ExplorationSource, GoalCounts

__all__ = ["ExplorationSource", "GoalCounts", "arrange", "slots_due"]
