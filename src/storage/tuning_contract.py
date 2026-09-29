"""What the tuning records hold, as the code reads them.

The assistant writes the records by editing the files; the code only reads
them, apart from the summary it generates.
"""

from typing import Protocol

from ..entities.tuning import Belief, Cycle, ExplorationPlan, Report, StoryLabel


class TuningError(Exception):
    """A tuning record is missing, malformed or inconsistent. The message
    names the file and the field."""


class TuningRecords(Protocol):
    def exploration_plan(self) -> ExplorationPlan:
        """The plan; the empty plan when there is none."""
        ...

    def beliefs(self) -> list[Belief]: ...

    def cycles(self) -> list[Cycle]:
        """Ordered by number."""
        ...

    def open_cycle(self) -> Cycle:
        """The one open cycle; TuningError unless there is exactly one."""
        ...

    def reports(self) -> list[Report]:
        """Ordered by id, which is by date."""
        ...

    def story_labels(self) -> dict[int, StoryLabel]:
        """The newest label of each record."""
        ...

    def write_summary(self, markdown: str) -> None: ...
