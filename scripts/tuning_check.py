"""Check the tuning records under ``tuning/`` (``TUNING_DIR``): that they
load, that they agree with each other, that the prompts on disk are the ones
the open cycle records, and that no report or closed cycle was rewritten.

A prompt edited outside the routine is the check's main catch: the videos
made after the edit would be credited to the wrong cycle. The edit is not
undone here; the assistant asks why, records it in the open cycle's
``outside_changes`` and the check passes again.

Prints one line per check and exits 0, or 1 when any failed.

Usage:
    uv run python scripts/tuning_check.py
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import yaml

from src.core.paths import tuning_dir
from src.entities.tuning import (
    PROMPT_FILES,
    Belief,
    Cycle,
    ExplorationPlan,
    Report,
)
from src.prompts.loader import PROMPTS_DIR, fingerprint
from src.storage import FileTuningRecords, TuningError


@dataclass(frozen=True)
class Records:
    root: Path
    prompts_dir: Path
    plan: ExplorationPlan
    beliefs: list[Belief]
    cycles: list[Cycle]
    reports: list[Report]


@dataclass
class Check:
    number: int
    name: str
    problems: list[str] = field(default_factory=list)


def _open_cycle(records: Records) -> Optional[Cycle]:
    """The newest open cycle; check 2 reports when there is not exactly one."""
    open_cycles = [c for c in records.cycles if c.is_open]
    return open_cycles[-1] if open_cycles else None


def _one_open_cycle(records: Records) -> list[str]:
    numbers = [c.number for c in records.cycles]
    problems = []
    if numbers != list(range(1, len(numbers) + 1)):
        problems.append(
            f"os ciclos devem ir de 1 a {len(numbers)} sem lacunas: {numbers}"
        )
    open_cycles = [c.number for c in records.cycles if c.is_open]
    if len(open_cycles) != 1:
        problems.append(
            f"{len(open_cycles)} ciclos abertos {open_cycles}; deve haver exatamente um"
        )
    elif open_cycles[0] != max(numbers):
        problems.append(
            f"o ciclo aberto é o {open_cycles[0]}, mas o mais recente é o {max(numbers)}"
        )
    # Cycle 0 is the empty plan: no exploration.yaml, nothing to compare.
    elif records.plan.cycle not in (0, open_cycles[0]):
        problems.append(
            f"exploration.yaml diz ciclo {records.plan.cycle}; o aberto é o {open_cycles[0]}"
        )
    return problems


def _unique_ids(records: Records) -> list[str]:
    groups = {
        "experimento": [e.id for e in records.plan.experiments],
        "crença": [b.id for b in records.beliefs],
        "relatório": [r.id for r in records.reports],
    }
    return [
        f"{kind} {id_} aparece {count} vezes"
        for kind, ids in groups.items()
        for id_, count in sorted(Counter(ids).items())
        if count > 1
    ]


def _experiments(records: Records) -> list[str]:
    beliefs = {b.id for b in records.beliefs}
    experiments = {e.id: e for e in records.plan.experiments}
    problems = []
    for experiment in records.plan.experiments:
        if experiment.belief and experiment.belief not in beliefs:
            problems.append(
                f"{experiment.id} testa a crença {experiment.belief}, que não existe"
            )
        if experiment.replaces:
            replaced = experiments.get(experiment.replaces)
            if replaced is None or replaced.status != "closed":
                problems.append(
                    f"{experiment.id} substitui {experiment.replaces},"
                    " que não é um experimento fechado"
                )
    return problems


def _beliefs(records: Records) -> list[str]:
    return [
        f"{belief.id} não tem a entrada 'entered' no histórico"
        for belief in records.beliefs
        if not any(event.event == "entered" for event in belief.history)
    ]


def _reports(records: Records) -> list[str]:
    cycles = {c.number: c for c in records.cycles}
    report_ids = [r.id for r in records.reports]
    problems = []
    for report in records.reports:
        cycle = cycles.get(report.cycle)
        if cycle is None:
            problems.append(f"{report.id} é do ciclo {report.cycle}, que não existe")
        elif report.id not in cycle.reports:
            problems.append(
                f"{report.id} não está na lista reports do ciclo {report.cycle}"
            )
        if report.corrects and not (
            report.corrects in report_ids and report.corrects < report.id
        ):
            problems.append(
                f"{report.id} corrige {report.corrects}, que não é um relatório anterior"
            )
    for cycle in records.cycles:
        problems += [
            f"o ciclo {cycle.number} lista {id_}, que não existe"
            for id_ in cycle.reports
            if id_ not in report_ids
        ]
    return problems


def _prompt_changes(records: Records) -> list[str]:
    # A finding has no id of its own: it is named by the report it is in.
    known = {
        "finding": {r.id for r in records.reports},
        "belief": {b.id for b in records.beliefs},
        "experiment": {e.id for e in records.plan.experiments},
    }
    return [
        f"ciclo {cycle.number}: a mudança em {change.prompt} se apoia em"
        f" {change.justification.kind} {change.justification.ref}, que não existe"
        for cycle in records.cycles
        for change in cycle.changes
        if change.justification.ref not in known[change.justification.kind]
    ]


def _prompts_match(records: Records) -> list[str]:
    cycle = _open_cycle(records)
    if cycle is None:
        return ["sem ciclo aberto, não há versões com que comparar"]
    problems = []
    for name, template in PROMPT_FILES.items():
        recorded = getattr(cycle.prompts, name)
        on_disk = (
            fingerprint(template, str(records.prompts_dir))
            if (records.prompts_dir / template).exists()
            else None
        )
        explained = any(
            change.prompt == name and change.to == on_disk
            for change in cycle.outside_changes
        )
        if recorded != on_disk and not explained:
            problems.append(
                f"prompt {name} mudou fora da rotina:"
                f" {recorded or 'ausente'} → {on_disk or 'ausente'}"
            )
    return problems


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout


def _written_records_unchanged(records: Records) -> list[str]:
    # New files are not in HEAD, so only edits and deletions show; a rename
    # shows as both. The cycle that was open at HEAD may change: it is the
    # one being worked on, and closing it is an edit.
    changed = _git(
        records.root,
        "diff",
        "--relative",
        "--name-only",
        "--no-renames",
        "--diff-filter=MD",
        "HEAD",
        "--",
        "reports",
        "cycles",
    ).split()
    problems = []
    for path in changed:
        if path.startswith("cycles/"):
            at_head = yaml.safe_load(_git(records.root, "show", f"HEAD:./{path}"))
            if at_head.get("closed") is None:
                continue
            problems.append(f"{path} já estava fechado e mudou")
        else:
            problems.append(f"{path} mudou depois de gravado")
    if problems:
        problems.append("uma correção é um relatório novo com corrects")
    return problems


CHECKS: list[tuple[int, str, Callable[[Records], list[str]]]] = [
    (2, "um só ciclo aberto, o mais recente, o de exploration.yaml", _one_open_cycle),
    (3, "ids únicos", _unique_ids),
    (4, "experimentos apontam para crenças e experimentos válidos", _experiments),
    (5, "crenças com a entrada no histórico", _beliefs),
    (6, "relatórios ligados aos seus ciclos", _reports),
    (7, "mudanças de prompt com justificativa existente", _prompt_changes),
    (8, "prompts em disco iguais aos do ciclo aberto", _prompts_match),
    (
        9,
        "relatórios e ciclos fechados sem mudança desde o último commit",
        _written_records_unchanged,
    ),
]
LOAD = "os registros carregam"


def run_checks(root: Path, prompts_dir: Path) -> list[Check]:
    """Every check in order; only the first when the records do not load,
    since the rest would have nothing to look at."""
    source = FileTuningRecords(root)
    try:
        records = Records(
            root=root,
            prompts_dir=prompts_dir,
            plan=source.exploration_plan(),
            beliefs=source.beliefs(),
            cycles=source.cycles(),
            reports=source.reports(),
        )
        source.story_labels()
    except TuningError as e:
        return [Check(1, LOAD, [str(e)])]
    return [Check(1, LOAD)] + [
        Check(number, name, check(records)) for number, name, check in CHECKS
    ]


def main() -> int:
    checks = run_checks(Path(tuning_dir()), Path(PROMPTS_DIR))
    ran = {c.number for c in checks}
    for check in checks:
        print(f"{'FALHOU' if check.problems else 'ok':<6} {check.number}. {check.name}")
        for problem in check.problems:
            print(f"         {problem}")
    for number, name, _ in CHECKS:
        if number not in ran:
            print(f"{'—':<6} {number}. {name} (não verificado)")
    failed = sum(1 for c in checks if c.problems)
    print(f"\n{failed} verificação(ões) falharam" if failed else "\ntudo certo")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
