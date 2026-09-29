"""Settling a cycle (US5): the base videos of one cycle against the previous
one's, each experiment's progress toward its sample, and the share of the
production that went to exploring."""

from datetime import timedelta

import pytest

from src.capabilities.tuning import (
    ambiguous_goals,
    compare_cycles,
    experiment_progress,
    prompt_drift,
    share_achieved,
)
from src.entities.tuning import (
    Experiment,
    ExplorationPlan,
    OutsideChange,
    Stamp,
)

from .tuning_videos import DAY0, cycle, recipe, video


def _videos(first_id: int, count: int, **kwargs) -> list:
    return [video(first_id + i, **kwargs) for i in range(count)]


def _experiment(id_: str, *, opened_day: int = 0, target: int = 10, status="open"):
    return Experiment(
        id=id_,
        status=status,
        kind="unexplored",
        question="Histórias de vizinhos funcionam?",
        motivation="Nunca foram feitas.",
        looks_like="Conflito com um vizinho.",
        sample_target=target,
        decision_rule="Funciona acima de 1,2.",
        opened=Stamp(cycle=1, date=DAY0 + timedelta(days=opened_day)),
    )


# ------------------------------------------------------------------ cycles


def test_only_settled_base_videos_count_for_a_cycle():
    cycles = [cycle(1, closed=DAY0), cycle(2)]
    videos = [
        *_videos(1, 20, cycle=1, relative=1.0),
        *_videos(100, 20, cycle=2, relative=2.0, goal="base"),
        *_videos(200, 5, cycle=2, relative=0.1, goal="E001"),  # exploring
        *_videos(300, 5, cycle=2, settled=False),  # too young
    ]

    comparison = compare_cycles(videos, cycles)

    assert (comparison.current.cycle, comparison.current.base_videos) == (2, 20)
    assert comparison.current.median_relative == pytest.approx(2.0)
    assert (comparison.previous.cycle, comparison.previous.base_videos) == (1, 20)
    assert comparison.previous.median_relative == pytest.approx(1.0)
    assert comparison.verdict_possible is True
    assert comparison.also_changed == []


def test_before_the_first_cycle_is_cycle_zero():
    # Nothing records its cycle yet: a video belongs to the newest cycle
    # deployed on or before the day it was made.
    cycles = [cycle(1, deployed=DAY0 + timedelta(days=30))]
    videos = [
        *_videos(1, 3, day=10),
        *_videos(10, 2, day=30),
        *_videos(20, 1, day=31, cycle=1),
    ]

    comparison = compare_cycles(videos, cycles)

    assert (comparison.current.cycle, comparison.current.base_videos) == (1, 3)
    assert (comparison.previous.cycle, comparison.previous.base_videos) == (0, 3)


def test_below_twenty_on_either_side_there_is_no_verdict():
    cycles = [cycle(1, closed=DAY0), cycle(2)]
    videos = [*_videos(1, 25, cycle=1), *_videos(100, 14, cycle=2)]

    comparison = compare_cycles(videos, cycles)

    assert comparison.verdict_possible is False
    assert "14 vídeos de base assentados no ciclo 2" in comparison.reason
    assert "o mínimo é 20" in comparison.reason


def test_a_model_changed_with_the_prompts_is_named():
    cycles = [cycle(1, closed=DAY0), cycle(2, writer="claude")]
    videos = [
        *_videos(1, 20, cycle=1, recipe=recipe(writer="kimi")),
        *_videos(100, 20, cycle=2, recipe=recipe(writer="claude")),
    ]

    comparison = compare_cycles(videos, cycles)

    assert comparison.also_changed == ["writer_model"]
    assert comparison.verdict_possible is True
    assert "writer_model" in comparison.reason


def test_without_recipes_the_cycles_settings_are_compared():
    cycles = [cycle(1, closed=DAY0), cycle(2, writer="claude")]
    videos = [*_videos(1, 20, cycle=1), *_videos(100, 20, cycle=2)]

    assert compare_cycles(videos, cycles).also_changed == ["writer_model"]


def test_a_prompt_that_differs_from_its_cycle_is_drift_unless_explained():
    open_cycle = cycle(1, story="a" * 12)
    on_disk = {
        "story": "d" * 12,
        "evaluate_story": "b" * 12,
        "generate_hashtags": "c" * 12,
        "evaluate_exploration": None,
    }

    drift = prompt_drift(open_cycle, on_disk)

    assert [(d.prompt, d.recorded, d.on_disk) for d in drift] == [
        ("story", "a" * 12, "d" * 12)
    ]
    explained = open_cycle.model_copy(
        update={
            "outside_changes": [
                OutsideChange.model_validate(
                    {
                        "detected": DAY0,
                        "prompt": "story",
                        "from": "a" * 12,
                        "to": "d" * 12,
                        "reason": "Correção de digitação.",
                    }
                )
            ]
        }
    )
    assert prompt_drift(explained, on_disk) == []


# ------------------------------------------------------------- experiments


def test_an_experiment_shows_its_settled_videos_and_the_days_left():
    plan = ExplorationPlan(
        cycle=1, share=0.25, experiments=[_experiment("E001", opened_day=0)]
    )
    videos = [
        video(1, day=1, goal="E001", relative=0.5),
        video(2, day=3, goal="E001", relative=1.5),
        video(3, day=8, goal="E001", settled=False),
        video(4, day=9, goal="E001", settled=False),
        video(5, day=9),  # base
    ]

    [progress] = experiment_progress(videos, plan, DAY0 + timedelta(days=10))

    assert (progress.id, progress.produced, progress.settled, progress.target) == (
        "E001",
        4,
        2,
        10,
    )
    assert progress.median_relative == pytest.approx(1.0)
    assert progress.videos == [1, 2]
    # Four videos in ten days: eight more settled need twenty days.
    assert progress.days_to_target == 20
    assert progress.target_reached is False


def test_an_experiment_without_videos_has_no_estimate():
    plan = ExplorationPlan(cycle=1, share=0.25, experiments=[_experiment("E001")])

    [progress] = experiment_progress([video(1)], plan, DAY0 + timedelta(days=5))

    assert (progress.produced, progress.days_to_target) == (0, None)
    assert progress.median_relative is None


def test_an_experiment_at_its_target_is_reached():
    plan = ExplorationPlan(
        cycle=1, share=0.25, experiments=[_experiment("E001", target=2)]
    )
    videos = _videos(1, 3, goal="E001")

    [progress] = experiment_progress(videos, plan, DAY0 + timedelta(days=5))

    assert (progress.target_reached, progress.days_to_target) == (True, 0)


def test_only_open_experiments_are_followed_in_priority_order():
    plan = ExplorationPlan(
        cycle=1,
        share=0.25,
        experiments=[
            _experiment("E002"),
            Experiment(id="E003", status="backlog", question="?", motivation="!"),
            _experiment("E001"),
        ],
    )

    progress = experiment_progress([], plan, DAY0)

    assert [p.id for p in progress] == ["E002", "E001"]


def test_the_share_achieved_counts_from_when_the_share_took_effect():
    plan = ExplorationPlan(cycle=1, share=0.25, share_since=DAY0 + timedelta(days=10))
    videos = [
        *_videos(1, 5, day=5, goal="E001"),  # before the share
        *_videos(10, 6, day=10),
        video(20, day=11, goal="E001"),
        video(21, day=12, goal="E002", settled=False),
    ]

    assert share_achieved(videos, plan) == pytest.approx(0.25)
    assert share_achieved(videos, plan.model_copy(update={"share_since": None})) is None
    later = plan.model_copy(update={"share_since": DAY0 + timedelta(days=50)})
    assert share_achieved(videos, later) is None


def test_a_goal_that_names_no_experiment_is_ambiguous():
    plan = ExplorationPlan(cycle=1, share=0.25, experiments=[_experiment("E001")])
    videos = [
        video(1),
        video(2, goal="base"),
        video(3, goal="E001"),
        video(4, goal="E009"),
    ]

    assert ambiguous_goals(videos, plan) == [4]
