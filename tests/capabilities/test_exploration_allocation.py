"""How the daily run spends its exploration share: how many slots a day gets
and which stories take them. Pure, over plans and candidates."""

from datetime import date

import pytest

from src.capabilities.exploration import GoalCounts, arrange, slots_due
from src.entities.reddit_post import RedditPost
from src.entities.story_candidate import EvaluatedStory, ExplorationFit
from src.entities.tuning import ExplorationPlan
from tests.proxies.test_evaluate_exploration import experiment

NONE_YET = GoalCounts(total=0, exploration=0)


def plan(*ids: str, share=0.25, min_fit=70, closed=()) -> ExplorationPlan:
    experiments = [experiment(i) for i in ids]
    experiments += [
        experiment(i).model_copy(update={"status": "backlog"}) for i in closed
    ]
    return ExplorationPlan(
        cycle=2,
        share=share,
        share_since=date(2026, 9, 29),
        min_fit=min_fit,
        experiments=experiments,
    )


def story(name: str, verdict="Boa", experiment=None, fit=0.0) -> EvaluatedStory:
    return EvaluatedStory(
        post=RedditPost(title=name, content="body", url=f"url-{name}"),
        evaluation={"veredito": verdict},
        exploration=ExplorationFit(experiment, fit) if experiment or fit else None,
    )


def names(stories) -> list[str]:
    return [s.post.title for s in stories]


def goals(stories) -> list[str]:
    return [s.goal for s in stories]


# ------------------------------------------------------------------ slots_due


def test_a_quarter_of_three_a_day_is_one_one_none_one():
    counts, sequence = NONE_YET, []
    for _ in range(4):
        slots = slots_due(0.25, counts, 3)
        sequence.append(slots)
        counts = GoalCounts(counts.total + 3, counts.exploration + slots)

    assert sequence == [1, 1, 0, 1]


def test_twelve_days_of_three_come_to_nine_for_exploration():
    counts = NONE_YET
    for _ in range(12):
        slots = slots_due(0.25, counts, 3)
        assert slots <= 1
        counts = GoalCounts(counts.total + 3, counts.exploration + slots)

    assert counts.total == 36
    assert abs(counts.exploration - 9) <= 1


def test_a_day_that_filled_nothing_is_made_up_within_the_daily_ceiling():
    # Two days made, one slot each due, neither filled.
    behind = GoalCounts(total=6, exploration=0)

    assert slots_due(0.25, behind, 3) == 1  # the ceiling, not the 2 owed
    # With a larger day the ceiling grows and the debt is paid.
    assert slots_due(0.25, behind, 8) == 2


def test_ahead_of_the_share_no_slot_is_due():
    assert slots_due(0.25, GoalCounts(total=3, exploration=3), 3) == 0


@pytest.mark.parametrize("share, target", [(0.0, 3), (0.25, 0)])
def test_no_share_or_no_target_means_no_slots(share, target):
    assert slots_due(share, NONE_YET, target) == 0


# -------------------------------------------------------------------- arrange


def test_the_slot_goes_to_the_best_fitting_story_of_the_first_experiment():
    candidates = [
        story("base 1"),
        story("fits", experiment="E001", fit=75),
        story("fits best", verdict="Mediana", experiment="E001", fit=90),
        story("base 2"),
    ]

    arranged, slots = arrange(candidates, plan("E001"), NONE_YET, 3)

    assert slots == 1
    # The chosen story first, then the base ones in the order received; the
    # story below "Boa" that was not chosen is left out.
    assert names(arranged) == ["fits best", "base 1", "fits", "base 2"]
    assert goals(arranged) == ["E001", "base", "base", "base"]


def test_the_first_experiment_in_the_file_takes_the_slot_when_both_have_stories():
    candidates = [
        story("for E002", experiment="E002", fit=95),
        story("for E001", experiment="E001", fit=80),
        story("base"),
    ]

    arranged, _ = arrange(candidates, plan("E001", "E002"), NONE_YET, 3)

    assert names(arranged)[0] == "for E001"
    assert goals(arranged) == ["E001", "base", "base"]


def test_a_first_experiment_without_a_story_leaves_the_slot_to_the_next():
    candidates = [story("base"), story("for E002", experiment="E002", fit=72)]

    arranged, _ = arrange(candidates, plan("E001", "E002"), NONE_YET, 3)

    assert names(arranged) == ["for E002", "base"]
    assert goals(arranged) == ["E002", "base"]


def test_a_story_below_the_minimum_fit_does_not_take_the_slot():
    candidates = [story("base"), story("almost", experiment="E001", fit=69)]

    arranged, slots = arrange(candidates, plan("E001"), NONE_YET, 3)

    assert slots == 1
    assert names(arranged) == ["base", "almost"]
    assert goals(arranged) == ["base", "base"]


def test_a_good_base_story_that_fits_takes_only_the_exploration_slot():
    candidates = [story("both", experiment="E001", fit=88), story("base")]

    arranged, _ = arrange(candidates, plan("E001"), NONE_YET, 2)

    assert names(arranged) == ["both", "base"]
    assert goals(arranged) == ["E001", "base"]


def test_stories_only_the_exploration_grade_brought_are_left_out_unless_chosen():
    candidates = [
        story("base"),
        story("chosen", verdict="Mediana", experiment="E001", fit=90),
        story("second", verdict="Mediana", experiment="E001", fit=85),
    ]

    arranged, _ = arrange(candidates, plan("E001"), NONE_YET, 3)

    assert names(arranged) == ["chosen", "base"]


def test_the_slots_are_returned_even_when_no_story_fills_them():
    arranged, slots = arrange(
        [story("base 1"), story("base 2")], plan("E001"), NONE_YET, 2
    )

    assert slots == 1
    assert goals(arranged) == ["base", "base"]


def test_without_an_open_experiment_the_candidates_come_back_untouched():
    # No verdicts: the stand-ins of the flow tests, and the golden run's.
    candidates = [
        EvaluatedStory(post=RedditPost(title=n, content="", url=n)) for n in "ab"
    ]

    for without in (plan(closed=("E001",)), ExplorationPlan.empty()):
        arranged, slots = arrange(candidates, without, NONE_YET, 2)
        assert (arranged, slots) == (candidates, 0)


def test_with_no_share_the_open_experiments_get_no_slot():
    candidates = [
        story("base"),
        story("fits", verdict="Mediana", experiment="E001", fit=99),
    ]

    arranged, slots = arrange(candidates, plan("E001", share=0), NONE_YET, 2)

    assert (names(arranged), slots) == (["base"], 0)
