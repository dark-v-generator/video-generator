"""Where the daily run reads the exploration plan from.

The plan is read again at every run, because the bot stays up between deploys
and the plan changes with the reports. A plan that does not load stops the
run, naming the file and the field.
"""

from typing import Protocol

from ...entities.history import GoalCounts
from ...entities.tuning import ExplorationPlan

# Kept with the history, whose contract counts them; the allocation reads them.
__all__ = ["ExplorationSource", "GoalCounts"]


class ExplorationSource(Protocol):
    def plan(self) -> ExplorationPlan:
        """The current plan; the empty plan when there is none."""
        ...
