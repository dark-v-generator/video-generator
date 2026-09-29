"""The tuning records load from their files, or stop naming the file and field."""

import shutil
from datetime import date
from pathlib import Path

import pytest
import yaml

from src.storage import FileTuningRecords, TuningError

VALID = Path(__file__).parent.parent / "fixtures" / "tuning" / "valid"


@pytest.fixture
def root(tmp_path) -> Path:
    shutil.copytree(VALID, tmp_path / "tuning")
    return tmp_path / "tuning"


def test_every_record_loads():
    records = FileTuningRecords(VALID)

    plan = records.exploration_plan()
    assert (plan.cycle, plan.share, plan.min_fit) == (2, 0.25, 70)
    assert [b.id for b in records.beliefs()] == ["B001", "B002"]
    assert [c.number for c in records.cycles()] == [1, 2]
    assert records.open_cycle().number == 2
    assert [r.id for r in records.reports()] == ["R-2026-10-01", "R-2026-10-15"]
    assert records.cycles()[0].closing.decision == "close"


def test_a_report_holds_what_its_reading_view_draws():
    # The page is rebuilt from the report alone: the weekly chart and each
    # experiment's forecast have to be in it.
    report = FileTuningRecords(VALID).reports()[-1]

    assert [(w.week, w.median_views) for w in report.weekly_reach] == [
        (date(2026, 9, 28), 584),
        (date(2026, 10, 5), 610),
    ]
    assert report.cycle_state.experiments[0].days_to_target == 19
    older = FileTuningRecords(VALID).reports()[0]
    assert older.weekly_reach == []
    assert older.cycle_state.experiments == []


def test_open_experiments_keep_the_file_order(root):
    path = root / "exploration.yaml"
    plan = yaml.safe_load(path.read_text(encoding="utf-8"))
    # E001 reopened: the open ones come back in file order, not by id.
    plan["experiments"][1].update(status="open", outcome=None)
    path.write_text(yaml.safe_dump(plan, allow_unicode=True), encoding="utf-8")

    plan = FileTuningRecords(root).exploration_plan()

    assert [e.id for e in plan.open()] == ["E002", "E001"]
    assert [e.id for e in plan.experiments] == ["E002", "E001", "E003"]


def test_no_plan_file_is_the_empty_plan(root):
    (root / "exploration.yaml").unlink()

    plan = FileTuningRecords(root).exploration_plan()

    assert (plan.cycle, plan.share, plan.experiments) == (0, 0, [])
    assert plan.open() == []


def test_missing_records_are_empty(tmp_path):
    records = FileTuningRecords(tmp_path)

    assert records.beliefs() == []
    assert records.cycles() == []
    assert records.reports() == []
    assert records.story_labels() == {}


def test_invalid_yaml_names_the_file(root):
    (root / "beliefs.yaml").write_text("beliefs: [unclosed\n", encoding="utf-8")

    with pytest.raises(TuningError, match=r"beliefs\.yaml: not valid YAML"):
        FileTuningRecords(root).beliefs()


def test_an_invalid_field_names_the_file_and_the_field(root):
    text = (root / "exploration.yaml").read_text(encoding="utf-8")
    (root / "exploration.yaml").write_text(
        text.replace("share: 0.25", "share: 0.8"), encoding="utf-8"
    )

    with pytest.raises(TuningError, match=r"exploration\.yaml: share: "):
        FileTuningRecords(root).exploration_plan()


def test_a_misspelt_key_is_an_error(root):
    text = (root / "cycles" / "002.yaml").read_text(encoding="utf-8")
    (root / "cycles" / "002.yaml").write_text(
        text.replace("deployed:", "deploy:"), encoding="utf-8"
    )

    with pytest.raises(TuningError, match=r"002\.yaml: deploy: "):
        FileTuningRecords(root).cycles()


def test_a_cycle_must_match_its_file_name(root):
    (root / "cycles" / "002.yaml").rename(root / "cycles" / "003.yaml")

    with pytest.raises(TuningError, match=r"003\.yaml: number: 2"):
        FileTuningRecords(root).cycles()


def test_a_report_must_match_its_file_name(root):
    (root / "reports" / "2026-10-15.yaml").rename(root / "reports" / "2026-10-16.yaml")

    with pytest.raises(TuningError, match=r"2026-10-16\.yaml: id: R-2026-10-15"):
        FileTuningRecords(root).reports()


def test_no_open_cycle_is_an_error(root):
    (root / "cycles" / "002.yaml").unlink()

    with pytest.raises(TuningError, match="0 open cycles"):
        FileTuningRecords(root).open_cycle()


def test_the_newest_label_wins():
    labels = FileTuningRecords(VALID).story_labels()

    assert labels[101].kind == "work_payback"
    assert labels[101].labelled_at == date(2026, 10, 15)
    assert labels[102].kind == "partner"


def test_a_bad_label_names_the_line(root):
    with (root / "story_labels.csv").open("a", encoding="utf-8") as f:
        f.write("abc,work,fought_back,reaction,2026-10-16,\n")

    with pytest.raises(TuningError, match=r"story_labels\.csv:5: record_id"):
        FileTuningRecords(root).story_labels()


def test_write_summary_writes_the_readme(root):
    FileTuningRecords(root).write_summary("# Ajuste\n")

    assert (root / "README.md").read_text(encoding="utf-8") == "# Ajuste\n"
