"""How far each open experiment is from an answer, and how much of the
production actually went to exploring."""

import math
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Optional

from ...entities.tuning import ExplorationPlan
from .relative import Video


@dataclass(frozen=True)
class ExperimentProgress:
    id: str
    produced: int
    settled: int
    target: int
    median_relative: Optional[float]
    # The settled videos, the ones a verdict would rest on.
    videos: list[int]
    days_to_target: Optional[int]
    target_reached: bool


def experiment_progress(
    videos: list[Video], plan: ExplorationPlan, today: date
) -> list[ExperimentProgress]:
    """Each open experiment, highest priority first. The days left assume
    the pace since it opened holds; with nothing produced there is no pace."""
    progress = []
    for experiment in plan.open():
        made = [v for v in videos if v.goal == experiment.id]
        final = [v for v in made if v.settled]
        relatives = [v.relative for v in final if v.relative is not None]
        target = experiment.sample_target
        reached = len(final) >= target
        if reached:
            days_left: Optional[int] = 0
        elif not made:
            days_left = None
        else:
            elapsed = max(1, (today - experiment.opened.date).days)
            days_left = math.ceil((target - len(final)) / (len(made) / elapsed))
        progress.append(
            ExperimentProgress(
                id=experiment.id,
                produced=len(made),
                settled=len(final),
                target=target,
                median_relative=median(relatives) if relatives else None,
                videos=[v.record_id for v in final],
                days_to_target=days_left,
                target_reached=reached,
            )
        )
    return progress


def share_achieved(videos: list[Video], plan: ExplorationPlan) -> Optional[float]:
    """The part of the videos made since the share took effect that went to
    an experiment; None before there is a share or a video to count."""
    if plan.share_since is None:
        return None
    since = [v for v in videos if v.made_on >= plan.share_since]
    if not since:
        return None
    return sum(1 for v in since if not v.is_base) / len(since)


def ambiguous_goals(videos: list[Video], plan: ExplorationPlan) -> list[int]:
    """Videos made for an experiment the plan does not have: their numbers
    cannot be credited to any question."""
    known = {e.id for e in plan.experiments}
    return [v.record_id for v in videos if not v.is_base and v.goal not in known]
