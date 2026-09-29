"""The daily run's exploration slots: what the run makes for the open
experiments, what it records, and what it says. Every capability is faked."""

import datetime

import pytest

from src.capabilities.writing import WriterError
from src.entities.reddit_post import RedditPost
from src.entities.story_candidate import EvaluatedStory, ExplorationFit
from src.entities.tuning import ExplorationPlan
from src.flows import daily_run as daily_run_module
from tests.fakes.exploration import FakeExplorationSource
from tests.fakes.memory_history import InMemoryHistoryStore
from tests.flows.test_daily_run import NOW, ScriptedWriter, build
from tests.flows.test_daily_run_history import EVALUATION, records
from tests.proxies.test_evaluate_exploration import experiment

PLAN = ExplorationPlan(
    cycle=2,
    share=0.25,
    share_since=NOW.date(),
    min_fit=70,
    experiments=[experiment("E001")],
)


def candidate(title: str, verdict="Boa", fit=None) -> EvaluatedStory:
    return EvaluatedStory(
        post=RedditPost(title=title, content="body", community="r/t", url=title),
        evaluation={**EVALUATION, "veredito": verdict},
        exploration=ExplorationFit("E001", fit) if fit is not None else None,
    )


def day(fitting=True) -> list[EvaluatedStory]:
    """Four good base stories and, on most days, one only the experiment wants."""
    found = [candidate(f"Base {i}") for i in range(1, 5)]
    if fitting:
        found.insert(2, candidate("Luto", verdict="Mediana", fit=90))
    return found


def flow_for(tmp_path, found, *, plan=PLAN, history=None, **kw):
    flow = build(
        tmp_path,
        history=history or InMemoryHistoryStore(),
        exploration=FakeExplorationSource(plan),
        **kw,
    )
    flow.discovery.results = found
    return flow


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    async def sleep(delay):
        return None

    monkeypatch.setattr(daily_run_module.asyncio, "sleep", sleep)


def summary(flow):
    return flow.history.run_summary(flow.record.run_id)


@pytest.mark.asyncio
async def test_the_exploration_video_has_the_experiment_as_its_goal(tmp_path):
    flow = flow_for(tmp_path, day())

    await flow.generate(count=3, output_dir=flow.output_dir)

    made = records(flow.history, flow)
    assert [(r.title, r.goal) for r in made] == [
        ("Luto", "E001"),
        ("Base 1", "base"),
        ("Base 2", "base"),
    ]
    assert (summary(flow).exploration_slots, summary(flow).exploration_filled) == (
        1,
        1,
    )
    assert summary(flow).candidates_found == 5
    assert (
        "✅ Busca finalizada: 5 histórias disponíveis (1 de exploração). "
        "Iniciando geração de 3 vídeos."
    ) in flow.messages


@pytest.mark.asyncio
async def test_an_exploration_story_that_fails_to_write_gives_way_to_a_base_one(
    tmp_path,
):
    writer = ScriptedWriter(errors={"Luto": [WriterError("bad script")]})
    flow = flow_for(tmp_path, day(), writer=writer)

    await flow.generate(count=3, output_dir=flow.output_dir)

    made = records(flow.history, flow)
    assert [(r.title, r.goal) for r in made] == [
        ("Base 1", "base"),
        ("Base 2", "base"),
        ("Base 3", "base"),
    ]
    # The slot was kept for the experiment and is counted as not filled.
    assert (summary(flow).exploration_slots, summary(flow).exploration_filled) == (
        1,
        0,
    )


@pytest.mark.asyncio
async def test_a_day_without_a_fitting_story_is_all_base_with_the_slot_counted(
    tmp_path,
):
    flow = flow_for(tmp_path, day(fitting=False))

    await flow.run(count=3, output_dir=flow.output_dir)

    assert [r.goal for r in records(flow.history, flow)] == ["base"] * 3
    assert summary(flow).exploration_slots >= 1
    assert summary(flow).exploration_filled == 0
    assert (
        "✅ Busca finalizada: 4 histórias disponíveis (0 de exploração). "
        "Iniciando geração de vídeo e agendamento."
    ) in flow.messages


@pytest.mark.asyncio
async def test_a_story_in_parts_fills_one_slot(tmp_path):
    flow = flow_for(tmp_path, day(), writer=ScriptedWriter(parts=2))

    await flow.generate(count=3, output_dir=flow.output_dir)

    made = records(flow.history, flow)
    assert [r.goal for r in made] == ["E001", "E001"] + ["base"] * 4
    assert (summary(flow).exploration_slots, summary(flow).exploration_filled) == (
        1,
        1,
    )


@pytest.mark.asyncio
async def test_without_an_open_experiment_the_run_says_what_it_always_said(
    tmp_path,
):
    flow = flow_for(tmp_path, day(fitting=False), plan=ExplorationPlan.empty())

    await flow.generate(count=3, output_dir=flow.output_dir)

    assert (
        "✅ Busca finalizada: 4 histórias disponíveis. Iniciando geração de 3 vídeos."
    ) in flow.messages
    assert (summary(flow).exploration_slots, summary(flow).exploration_filled) == (
        0,
        0,
    )


@pytest.mark.asyncio
async def test_twelve_days_of_three_make_nine_exploration_videos_at_most_one_a_day(
    tmp_path,
):
    history = InMemoryHistoryStore()
    per_day = []
    for n in range(12):
        today = NOW + datetime.timedelta(days=n)
        flow = flow_for(tmp_path / str(n), day(), history=history)
        flow.now = lambda today=today: today

        await flow.generate(count=3, output_dir=flow.output_dir)

        per_day.append(summary(flow).exploration_filled)

    made = history.records.values()
    assert len(made) == 36
    explored = sum(r.goal == "E001" for r in made)
    assert abs(explored - 9) <= 1
    assert max(per_day) == 1
    assert history.goal_counts(PLAN.share_since).exploration == explored


@pytest.mark.parametrize("since", [NOW.date(), None])
@pytest.mark.asyncio
async def test_the_share_counts_only_the_videos_made_since_it_was_set(tmp_path, since):
    history = InMemoryHistoryStore()
    # Three days ago, under a larger share, one video made and it explored.
    earlier = flow_for(
        tmp_path / "before",
        day(),
        plan=PLAN.model_copy(update={"share": 0.5}),
        history=history,
    )
    earlier.now = lambda: NOW - datetime.timedelta(days=3)
    await earlier.generate(count=1, output_dir=earlier.output_dir)
    assert [r.goal for r in history.records.values()] == ["E001"]

    # Counted from then, today would owe nothing; the share starts today
    # (and a plan that does not say when it started, starts today too).
    today = flow_for(
        tmp_path / "today",
        day(),
        plan=PLAN.model_copy(update={"share_since": since}),
        history=history,
    )
    await today.generate(count=3, output_dir=today.output_dir)

    assert summary(today).exploration_slots == 1
