"""An exploration plan held in memory, counting how often the run reads it."""

from src.entities.tuning import ExplorationPlan


class FakeExplorationSource:
    def __init__(self, plan: ExplorationPlan):
        self._plan = plan
        self.reads = 0

    def plan(self) -> ExplorationPlan:
        self.reads += 1
        return self._plan
