"""A cycle's base videos against the previous cycle's, and the prompts that
moved since the cycle opened.

Only base videos compare: exploration videos are chosen for a question, not
for the prompts' idea of a good story. Only settled ones: a young video's
views are not its views yet.
"""

from dataclasses import dataclass
from statistics import median
from typing import Optional

from ...entities.tuning import PROMPT_FILES, Cycle
from .relative import Video

# What else shapes a video: when one of these changed with the prompts, a
# difference between the cycles is not the prompts' alone.
SETTINGS = ("writer_model", "grader_model", "rendering_strategy")


@dataclass(frozen=True)
class CycleSide:
    cycle: int
    base_videos: int
    median_relative: Optional[float]


@dataclass(frozen=True)
class CycleComparison:
    current: CycleSide
    previous: CycleSide
    also_changed: list[str]
    verdict_possible: bool
    reason: str


@dataclass(frozen=True)
class PromptDrift:
    prompt: str
    recorded: Optional[str]
    on_disk: Optional[str]


def cycle_of(video: Video, cycles: list[Cycle]) -> int:
    """The cycle the video recorded; before videos recorded it, the newest
    cycle deployed on or before the day it was made. Zero is before the
    first cycle."""
    if video.cycle is not None:
        return video.cycle
    deployed = [
        c.number
        for c in cycles
        if c.deployed is not None and c.deployed <= video.made_on
    ]
    return max(deployed, default=0)


def _setting_values(
    videos: list[Video], cycle: Optional[Cycle], setting: str
) -> set[str]:
    """What the videos were made with; the cycle's intent when they do not
    say (videos imported without a recipe)."""
    made_with = {
        getattr(v.row.record.recipe, setting)
        for v in videos
        if v.row.record.recipe and getattr(v.row.record.recipe, setting)
    }
    if made_with or cycle is None:
        return made_with
    return {getattr(cycle.settings, setting)}


def compare_cycles(
    videos: list[Video], cycles: list[Cycle], minimum: int = 20
) -> CycleComparison:
    """The open cycle against the one before it. Fewer than ``minimum``
    settled base videos on either side and there is no verdict to give."""
    open_cycles = [c for c in cycles if c.is_open]
    if not open_cycles:
        raise ValueError("no open cycle to compare")
    current = open_cycles[-1].number
    numbers = {"current": current, "previous": current - 1}
    by_number = {c.number: c for c in cycles}
    sides, members = {}, {}
    for side, number in numbers.items():
        members[side] = [
            v
            for v in videos
            if v.settled and v.is_base and cycle_of(v, cycles) == number
        ]
        relatives = [v.relative for v in members[side] if v.relative is not None]
        sides[side] = CycleSide(
            cycle=number,
            base_videos=len(members[side]),
            median_relative=median(relatives) if relatives else None,
        )
    also_changed = []
    for setting in SETTINGS:
        values = [
            _setting_values(members[side], by_number.get(number), setting)
            for side, number in numbers.items()
        ]
        if all(values) and values[0] != values[1]:
            also_changed.append(setting)

    short = [
        f"{sides[side].base_videos} vídeos de base assentados no ciclo {number};"
        f" o mínimo é {minimum}"
        for side, number in numbers.items()
        if sides[side].base_videos < minimum
    ]
    if short:
        reason = "; ".join(short)
    elif also_changed:
        reason = (
            f"também mudou {', '.join(also_changed)}:"
            " o efeito não é atribuível só aos prompts"
        )
    else:
        reason = (
            f"{sides['current'].base_videos} e {sides['previous'].base_videos}"
            " vídeos de base assentados; só os prompts mudaram"
        )
    return CycleComparison(
        current=sides["current"],
        previous=sides["previous"],
        also_changed=also_changed,
        verdict_possible=not short,
        reason=reason,
    )


def prompt_drift(cycle: Cycle, on_disk: dict[str, Optional[str]]) -> list[PromptDrift]:
    """The prompts whose version on disk is not the one the cycle recorded,
    leaving out the edits already explained in its ``outside_changes``.
    ``on_disk`` has each prompt's fingerprint, None when the file is absent."""
    drift = []
    for name in PROMPT_FILES:
        recorded = getattr(cycle.prompts, name)
        found = on_disk.get(name)
        explained = any(
            change.prompt == name and change.to == found
            for change in cycle.outside_changes
        )
        if recorded != found and not explained:
            drift.append(PromptDrift(prompt=name, recorded=recorded, on_disk=found))
    return drift
