"""The tuning records as files under one directory (TUNING_DIR).

Every call reads the disk again: the records are small, and the assistant
edits them between calls. A record that does not load stops whoever asked for
it, naming the file and the field, rather than being skipped.
"""

import csv
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from ..entities.tuning import Belief, Cycle, ExplorationPlan, Report, StoryLabel
from .tuning_contract import TuningError

M = TypeVar("M", bound=BaseModel)


class _Beliefs(BaseModel):
    beliefs: list[Belief] = []


def _validate(model: type[M], data: object, where: str) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc']) or '(record)'}: {error['msg']}"
            for error in e.errors()
        )
        raise TuningError(f"{where}: {problems}") from e


def _load(path: Path, model: type[M]) -> M:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise TuningError(f"{path}: not valid YAML: {e}") from e
    if not isinstance(data, dict):
        raise TuningError(f"{path}: expected a mapping at the top")
    return _validate(model, data, str(path))


class FileTuningRecords:
    def __init__(self, root: Path | str):
        self._root = Path(root)

    def exploration_plan(self) -> ExplorationPlan:
        path = self._root / "exploration.yaml"
        if not path.exists():
            return ExplorationPlan.empty()
        return _load(path, ExplorationPlan)

    # The name the daily run knows it by (ExplorationSource).
    plan = exploration_plan

    def beliefs(self) -> list[Belief]:
        path = self._root / "beliefs.yaml"
        if not path.exists():
            return []
        return _load(path, _Beliefs).beliefs

    def cycles(self) -> list[Cycle]:
        cycles = []
        for path in sorted((self._root / "cycles").glob("*.yaml")):
            cycle = _load(path, Cycle)
            if path.stem != f"{cycle.number:03d}":
                raise TuningError(
                    f"{path}: number: {cycle.number} does not match the file name"
                )
            cycles.append(cycle)
        return sorted(cycles, key=lambda c: c.number)

    def open_cycle(self) -> Cycle:
        open_cycles = [c for c in self.cycles() if c.is_open]
        if len(open_cycles) != 1:
            raise TuningError(
                f"{self._root / 'cycles'}: {len(open_cycles)} open cycles,"
                " expected exactly one"
            )
        return open_cycles[0]

    def reports(self) -> list[Report]:
        reports = []
        for path in sorted((self._root / "reports").glob("*.yaml")):
            report = _load(path, Report)
            if report.id != f"R-{path.stem}":
                raise TuningError(
                    f"{path}: id: {report.id} does not match the file name"
                )
            reports.append(report)
        return sorted(reports, key=lambda r: r.id)

    def story_labels(self) -> dict[int, StoryLabel]:
        path = self._root / "story_labels.csv"
        if not path.exists():
            return {}
        labels: dict[int, StoryLabel] = {}
        with path.open(newline="", encoding="utf-8") as f:
            # Line 1 is the header. On the same day, the later line wins.
            for line, row in enumerate(csv.DictReader(f), start=2):
                label = _validate(StoryLabel, row, f"{path}:{line}")
                newest = labels.get(label.record_id)
                if newest is None or label.labelled_at >= newest.labelled_at:
                    labels[label.record_id] = label
        return labels

    def write_summary(self, markdown: str) -> None:
        (self._root / "README.md").write_text(markdown, encoding="utf-8")
