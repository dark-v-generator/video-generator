"""The tuning check passes on consistent records and names the rule each
broken one breaks (US6, FR-022, FR-041)."""

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import tuning_check

FIXTURES = Path(__file__).parent.parent / "fixtures" / "tuning"
STORY = "7762c0b406eb"


def _git(directory: Path, *args: str) -> None:
    subprocess.run(
        [
            "git",
            "-C",
            str(directory),
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            *args,
        ],
        check=True,
        capture_output=True,
    )


def _commit(directory: Path) -> None:
    _git(directory, "add", "-A")
    _git(directory, "commit", "-qm", "records")


@pytest.fixture
def repo(tmp_path) -> Path:
    """The valid records committed in a repository of their own; each
    ``broken-*`` fixture holds only the files it changes."""
    shutil.copytree(FIXTURES / "valid", tmp_path / "tuning")
    _git(tmp_path, "init", "-q")
    _commit(tmp_path)
    return tmp_path


@pytest.fixture
def prompts(tmp_path) -> Path:
    shutil.copytree(FIXTURES / "prompts", tmp_path / "prompts")
    return tmp_path / "prompts"


def _failing(root: Path, prompts: Path) -> dict[int, list[str]]:
    return {
        check.number: check.problems
        for check in tuning_check.run_checks(root, prompts)
        if check.problems
    }


def _edit_yaml(path: Path, change) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")


def test_valid_records_pass_every_check(repo, prompts):
    checks = tuning_check.run_checks(repo / "tuning", prompts)

    assert [c.number for c in checks] == list(range(1, 10))
    assert all(not c.problems for c in checks)


@pytest.mark.parametrize(
    "broken, rule, wording",
    [
        ("broken-2-open-cycle", 2, "2 ciclos abertos"),
        ("broken-3-ids", 3, "B001"),
        ("broken-4-experiments", 4, "B099"),
        ("broken-5-beliefs", 5, "B002"),
        ("broken-6-reports", 6, "R-2026-10-15"),
        ("broken-7-changes", 7, "R-2026-09-01"),
    ],
)
def test_each_broken_record_fails_only_its_rule(repo, prompts, broken, rule, wording):
    shutil.copytree(FIXTURES / broken, repo / "tuning", dirs_exist_ok=True)
    _commit(repo)

    failing = _failing(repo / "tuning", prompts)

    assert list(failing) == [rule]
    assert wording in " ".join(failing[rule])


def test_a_record_that_does_not_load_stops_the_other_checks(repo, prompts):
    (repo / "tuning" / "beliefs.yaml").write_text("beliefs: [\n", encoding="utf-8")

    checks = tuning_check.run_checks(repo / "tuning", prompts)

    assert [c.number for c in checks] == [1]
    assert "beliefs.yaml" in checks[0].problems[0]


def test_a_prompt_edited_outside_the_routine_names_both_versions(repo, prompts):
    story = prompts / "story.jinja2"
    story.write_text(
        "{# edited #}\n" + story.read_text(encoding="utf-8"), encoding="utf-8"
    )
    on_disk = hashlib.sha256(story.read_bytes()).hexdigest()[:12]

    failing = _failing(repo / "tuning", prompts)

    assert failing == {8: [f"prompt story mudou fora da rotina: {STORY} → {on_disk}"]}


def test_an_explained_outside_change_passes(repo, prompts):
    story = prompts / "story.jinja2"
    story.write_text(
        "{# edited #}\n" + story.read_text(encoding="utf-8"), encoding="utf-8"
    )
    on_disk = hashlib.sha256(story.read_bytes()).hexdigest()[:12]
    _edit_yaml(
        repo / "tuning" / "cycles" / "002.yaml",
        lambda cycle: cycle["outside_changes"].append(
            {
                "detected": "2026-10-20",
                "prompt": "story",
                "from": STORY,
                "to": on_disk,
                "reason": "Corrigido um erro de digitação.",
            }
        ),
    )

    assert _failing(repo / "tuning", prompts) == {}


def test_a_prompt_the_cycle_does_not_know_is_an_outside_change(repo, prompts):
    (prompts / "evaluate_exploration.jinja2").write_text("new\n", encoding="utf-8")

    failing = _failing(repo / "tuning", prompts)

    assert list(failing) == [8]
    assert failing[8][0].startswith(
        "prompt evaluate_exploration mudou fora da rotina: ausente → "
    )


def test_an_old_report_changed_since_commit_fails(repo, prompts):
    _edit_yaml(
        repo / "tuning" / "reports" / "2026-10-01.yaml",
        lambda report: report["decision"].update(note="reescrito"),
    )

    failing = _failing(repo / "tuning", prompts)

    assert list(failing) == [9]
    assert "reports/2026-10-01.yaml" in failing[9][0]


def test_a_closed_cycle_changed_since_commit_fails(repo, prompts):
    _edit_yaml(
        repo / "tuning" / "cycles" / "001.yaml",
        lambda cycle: cycle["closing"].update(note="reescrito"),
    )

    failing = _failing(repo / "tuning", prompts)

    assert list(failing) == [9]
    assert "cycles/001.yaml" in failing[9][0]


def test_new_reports_and_the_open_cycle_may_change(repo, prompts):
    tuning = repo / "tuning"
    shutil.copy(
        tuning / "reports" / "2026-10-15.yaml", tuning / "reports" / "2026-10-29.yaml"
    )
    _edit_yaml(
        tuning / "reports" / "2026-10-29.yaml",
        lambda r: r.update(id="R-2026-10-29", cycle=2),
    )
    _edit_yaml(
        tuning / "cycles" / "002.yaml", lambda c: c["reports"].append("R-2026-10-29")
    )
    _git(repo, "add", "-A")  # staged, not committed: still new to HEAD

    assert _failing(tuning, prompts) == {}


def test_closing_the_cycle_that_was_open_is_not_a_rewrite(repo, prompts):
    tuning = repo / "tuning"
    shutil.copy(tuning / "cycles" / "002.yaml", tuning / "cycles" / "003.yaml")
    _edit_yaml(tuning / "cycles" / "002.yaml", lambda c: c.update(closed="2026-10-29"))
    _edit_yaml(
        tuning / "cycles" / "003.yaml",
        lambda c: c.update(number=3, opened="2026-10-29"),
    )
    _edit_yaml(tuning / "exploration.yaml", lambda p: p.update(cycle=3))

    assert _failing(tuning, prompts) == {}


def test_main_prints_one_line_per_check_and_exits_0(repo, prompts, monkeypatch, capsys):
    monkeypatch.setenv("TUNING_DIR", str(repo / "tuning"))
    monkeypatch.setattr(tuning_check, "PROMPTS_DIR", str(prompts))

    assert tuning_check.main() == 0

    lines = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in lines[:9]] == ["ok"] * 9
    assert [line.split()[1] for line in lines[:9]] == [f"{n}." for n in range(1, 10)]


def test_main_exits_1_and_lists_what_failed(repo, prompts, monkeypatch, capsys):
    monkeypatch.setenv("TUNING_DIR", str(repo / "tuning"))
    monkeypatch.setattr(tuning_check, "PROMPTS_DIR", str(prompts))
    (prompts / "story.jinja2").write_text("changed\n", encoding="utf-8")

    assert tuning_check.main() == 1

    out = capsys.readouterr().out
    assert "FALHOU 8." in out
    assert f"prompt story mudou fora da rotina: {STORY} → " in out
