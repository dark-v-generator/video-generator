"""The tuning report's numbers from the command line (US1, FR-013): the
history and the tuning records in, every figure the report needs out, or a
refusal when the data cannot support findings."""

import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import tuning_data
from src.entities.history import (
    Collection,
    PerformanceMetrics,
    PerformanceSnapshot,
    ProductionRecipe,
    PublishAttempt,
    VideoRecord,
)
from src.storage import SqliteHistoryStore

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tuning"
FIRST = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
COLLECTED = NOW - timedelta(hours=2)
PERIOD = ["--since", "2026-09-10", "--until", "2026-10-20"]
LABELLED = (1, 2)


def _record(history, day: int, *, collected: bool = True, failed: bool = False) -> int:
    created = FIRST + timedelta(days=day)
    record_id = history.add_video_record(
        VideoRecord(
            created_at=created,
            run_id=1,
            video_path=f"output/daily/{day}.mp4",
            title=f"História {day}",
            summary=f"Resumo {day}",
            post_url=f"https://reddit.com/r/x/comments/{day}/",
            recipe=ProductionRecipe(
                "s" * 12,
                "g" * 12,
                "kimi",
                "deepseek",
                "narration",
                "edge",
                1.2,
                "m",
                "v",
            ),
        ),
        None,
    )
    history.add_publish_attempt(
        record_id,
        PublishAttempt(
            attempted_at=created,
            status="failed" if failed else "scheduled",
            scheduled_at=None if failed else created + timedelta(hours=3),
            hashtags=[],
        ),
    )
    if collected:
        history.record_collection(
            Collection(COLLECTED, COLLECTED, 60, 1, 0, 0, 0),
            {
                record_id: PerformanceSnapshot(
                    taken_at=COLLECTED,
                    tiktok_video_id=f"v{day}",
                    metrics=PerformanceMetrics(views=100 * (1 + day % 3)),
                )
            },
            {},
        )
    return record_id


@pytest.fixture
def history(tmp_path, monkeypatch):
    """36 videos, one a day from 10 September: 33 settled by the collection
    two hours ago, three too young, plus one upload that never went out."""
    path = tmp_path / "history.sqlite"
    monkeypatch.setenv("HISTORY_DB_PATH", str(path))
    history = SqliteHistoryStore(str(path))
    for day in range(36):
        _record(history, day)
    _record(history, 20, collected=False, failed=True)
    return history


@pytest.fixture
def records(tmp_path, monkeypatch) -> Path:
    root = tmp_path / "tuning"
    shutil.copytree(FIXTURES / "valid", root)
    (root / "story_labels.csv").write_text(
        "record_id,kind,narrator_acts,title_promise,labelled_at,note\n"
        + "".join(f"{i},work,fought_back,reaction,2026-10-01,\n" for i in LABELLED),
        encoding="utf-8",
    )
    monkeypatch.setenv("TUNING_DIR", str(root))
    return root


@pytest.fixture(autouse=True)
def now(monkeypatch):
    monkeypatch.setattr(tuning_data, "now", lambda: NOW.astimezone())


def _package(capsys, *args: str) -> dict:
    assert tuning_data.main([*PERIOD, *args]) == 0
    return json.loads(capsys.readouterr().out)


def test_the_package_has_every_part_of_the_contract(history, records, capsys):
    package = _package(capsys)

    assert set(package) == {
        "generated_at",
        "period",
        "data_as_of",
        "cycle",
        "prompt_drift",
        "videos",
        "channel",
        "rows",
        "unlabelled",
        "cycle_comparison",
        "exploration",
    }
    assert package["period"] == {"since": "2026-09-10", "until": "2026-10-20"}
    assert package["data_as_of"].startswith("2026-10-20")
    assert package["cycle"]["number"] == 2
    assert set(package["cycle"]["prompts"]) == {
        "story",
        "evaluate_story",
        "generate_hashtags",
        "evaluate_exploration",
    }
    assert set(package["channel"]) == {"weekly", "lost_uploads"}
    assert set(package["cycle_comparison"]) == {
        "current",
        "previous",
        "also_changed",
        "verdict_possible",
        "reason",
    }
    assert set(package["exploration"]) == {
        "share_intended",
        "share_since",
        "share_achieved",
        "slots",
        "filled",
        "experiments",
    }
    assert set(package["rows"][0]) == {
        "record_id",
        "title",
        "summary",
        "published_at",
        "settled",
        "views",
        "relative",
        "neighbours",
        "grade_overall",
        "avg_watch_seconds",
        "retained_3s",
        "for_you_share",
        "new_followers",
        "goal",
        "exploration_experiment",
        "exploration_fit",
        "cycle",
        "story_prompt_version",
        "grading_prompt_version",
        "label",
    }


def test_the_videos_are_counted_by_whether_they_can_be_read(history, records, capsys):
    package = _package(capsys)

    assert package["videos"] == {
        "considered": 33,
        "excluded": {"unsettled": 3, "no_snapshot": 1, "ambiguous_goal": 0},
    }
    assert len(package["rows"]) == 37
    assert package["channel"]["lost_uploads"] == {
        "attempts_failed": 1,
        "never_published": 1,
    }
    settled = [r for r in package["rows"] if r["settled"]]
    assert all(r["relative"] is not None and r["neighbours"] == 10 for r in settled)
    first = package["rows"][0]
    assert (first["views"], first["relative"]) == (100, 0.5)  # neighbours at 200


def test_each_row_carries_its_label_and_the_rest_are_unlabelled(
    history, records, capsys
):
    package = _package(capsys)

    labels = {r["record_id"]: r["label"] for r in package["rows"]}
    assert labels[1] == {
        "kind": "work",
        "narrator_acts": "fought_back",
        "title_promise": "reaction",
    }
    assert package["unlabelled"] == list(range(3, 38))


def test_the_prompts_that_moved_since_the_cycle_opened_are_listed(
    history, records, capsys
):
    # The fixture's cycle records the fixture prompts, not the shipped ones.
    package = _package(capsys)

    assert {d["prompt"] for d in package["prompt_drift"]} >= {"story"}
    story = next(d for d in package["prompt_drift"] if d["prompt"] == "story")
    assert story["recorded"] == "7762c0b406eb"


def test_the_open_experiments_show_their_progress(history, records, capsys):
    package = _package(capsys)

    assert package["exploration"]["share_intended"] == 0.25
    assert package["exploration"]["share_since"] == "2026-10-15"
    assert [e["id"] for e in package["exploration"]["experiments"]] == ["E002"]
    assert package["exploration"]["experiments"][0]["produced"] == 0


def test_json_writes_the_same_package_to_a_file(history, records, capsys, tmp_path):
    printed = _package(capsys)
    target = tmp_path / "pack.json"

    assert tuning_data.main([*PERIOD, "--json", str(target)]) == 0

    assert json.loads(target.read_text(encoding="utf-8")) == printed


def test_an_old_collection_is_refused(history, records, capsys):
    assert tuning_data.main([*PERIOD, "--max-age-days", "0"]) == 2

    out, err = capsys.readouterr()
    assert out == ""
    assert len(err.strip().splitlines()) == 1
    assert "just prod-collect-performance" in err


def test_too_few_settled_videos_are_refused(history, records, capsys):
    assert tuning_data.main(["--days", "3"]) == 2

    out, err = capsys.readouterr()
    assert out == ""
    assert "0 vídeos assentados no período; o mínimo é 30" in err
    assert "--days" in err


def test_a_history_never_collected_is_refused(tmp_path, records, monkeypatch, capsys):
    monkeypatch.setenv("HISTORY_DB_PATH", str(tmp_path / "empty.sqlite"))

    assert tuning_data.main(PERIOD) == 2

    out, err = capsys.readouterr()
    assert out == ""
    assert "just prod-collect-performance" in err
