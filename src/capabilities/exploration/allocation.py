"""How many of the day's stories go to the open experiments, and which.

The share is a fraction of production, so a day of three at 25% is owed 0.75
of a slot. Rounding per day would give 33% or nothing; counting since the
share was set gives 1, 1, 0, 1 and corrects itself after a day no story fitted.
The counts come from the history, so there is no state to keep.
"""

import dataclasses
import math
from typing import Sequence

from ...entities.history import GoalCounts
from ...entities.story_candidate import EvaluatedStory
from ...entities.tuning import ExplorationPlan


def slots_due(share: float, counts: GoalCounts, target: int) -> int:
    """The slots today owes the share, given what was made since it was set.

    Capped at the share of today's target (at least one), so several empty
    days never turn a whole day into exploration.
    """
    if share <= 0 or target <= 0:
        return 0
    # Half up, not Python's round-half-even: 1.5 owed is 2.
    due = math.floor(share * (counts.total + target) + 0.5) - counts.exploration
    return max(0, min(due, max(1, math.ceil(share * target))))


def arrange(
    candidates: Sequence[EvaluatedStory],
    plan: ExplorationPlan,
    counts: GoalCounts,
    target: int,
) -> tuple[list[EvaluatedStory], int]:
    """The stories in the order the run makes them, and the slots kept.

    Each slot goes to the highest-priority open experiment that has a story
    fitting it well enough, and takes its best-fitting one; those come first,
    marked with the experiment. Then the stories good enough for the base, in
    the order received. A story only the exploration grade brought in is left
    out unless it took a slot. The slots are returned even when no story
    filled them, so the run can count what was missed.
    """
    experiments = plan.open()
    if not experiments:
        return list(candidates), 0
    slots = slots_due(plan.share, counts, target)

    chosen: list[EvaluatedStory] = []
    for _ in range(slots):
        for experiment in experiments:
            fitting = [
                c
                for c in candidates
                if c.exploration is not None
                and c.exploration.experiment == experiment.id
                and c.exploration.fit >= plan.min_fit
                and not any(c is taken for taken in chosen)
            ]
            if fitting:
                best = max(fitting, key=lambda c: c.exploration.fit)
                chosen.append(best)
                break

    base = [
        dataclasses.replace(c, goal="base")
        for c in candidates
        if c.base_worthy and not any(c is taken for taken in chosen)
    ]
    explored = [dataclasses.replace(c, goal=c.exploration.experiment) for c in chosen]
    return explored + base, slots
