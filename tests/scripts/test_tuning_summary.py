"""The generated summary of the tuning records (US6, FR-044)."""

import shutil
from pathlib import Path

import pytest

from scripts import tuning_summary
from src.storage import FileTuningRecords

VALID = Path(__file__).parent.parent / "fixtures" / "tuning" / "valid"
SECTIONS = [
    "## Ciclo aberto",
    "## Base",
    "## O que não funciona",
    "## Pistas e contestadas",
    "## Experimentos abertos",
    "## Fila de ideias",
    "## Ciclos",
    "## Relatórios",
]


@pytest.fixture
def summary() -> str:
    return tuning_summary.render(FileTuningRecords(VALID))


def _section(summary: str, heading: str) -> str:
    start = summary.index(heading + "\n")
    rest = summary[start + len(heading) + 1 :]
    following = [rest.index(h + "\n") for h in SECTIONS if h + "\n" in rest]
    return rest[: min(following)] if following else rest


def test_sections_come_in_the_contract_order(summary):
    positions = [summary.index(heading + "\n") for heading in SECTIONS]

    assert positions == sorted(positions)


def test_the_open_cycle_shows_its_prompts_and_share(summary):
    section = _section(summary, "## Ciclo aberto")

    assert "Ciclo 2, aberto em 2026-10-15, implantado em 2026-10-16." in section
    assert "| story | `7762c0b406eb` |" in section
    assert "| evaluate_exploration | — |" in section
    assert "25% da produção desde 2026-10-15, nota mínima 70" in section


def test_each_belief_shows_evidence_confidence_last_test_and_history(summary):
    base = _section(summary, "## Base")
    leads = _section(summary, "## Pistas e contestadas")

    assert "B001" in base and "B002" not in base
    assert "12 vídeos, relativo mediano 4,1×, de 2026-08-29 a 2026-10-14" in base
    assert "Confiança média" in base
    assert "último teste em 2026-10-15" in base
    assert "2026-10-15, ciclo 1: confirmada (R-2026-10-15). 12 vídeos, entra na base." in base
    assert "B002" in leads and "pista" in leads
    assert _section(summary, "## O que não funciona").strip() == "Nenhuma."


def test_experiments_show_the_open_ones_and_the_queue(summary):
    open_ = _section(summary, "## Experimentos abertos")
    queue = _section(summary, "## Fila de ideias")

    assert "### E002 — Histórias com desconhecidos funcionam quando o narrador reage?" in open_
    assert "Desafia a crença B002" in open_ and "substitui E001" in open_
    assert "E001" not in queue and "E003" in queue


def test_a_prompt_phrase_leads_to_its_cycle_and_justification(summary):
    cycles = _section(summary, "## Ciclos")
    cycle_2 = cycles[cycles.index("### Ciclo 2") : cycles.index("### Ciclo 1")]

    assert (
        "> Valorize histórias em que o narrador reage, porque a audiência fica"
        " para ver a reação."
    ) in cycle_2
    assert "`evaluate_story`, aprovada" in cycle_2
    assert "achado de R-2026-10-15: Títulos que prometem reação" in cycle_2
    assert "`story`, rejeitada: Pista fraca; esperar o experimento." in cycle_2


def test_closed_cycles_show_their_evaluation_and_closing(summary):
    cycles = _section(summary, "## Ciclos")
    cycle_1 = cycles[cycles.index("### Ciclo 1") :]

    assert "de 2026-10-01 a 2026-10-15" in cycle_1
    assert "nenhuma (linha de base)" in cycle_1
    assert "Avaliação: não avaliado" in cycle_1
    assert "recomendação fechar, decisão fechar" in cycle_1


def test_reports_list_recommendation_and_decision(summary):
    reports = _section(summary, "## Relatórios")

    assert "| R-2026-10-15 | 1 | 2026-08-29 a 2026-10-14 | fechar | fechar |" in reports
    assert reports.index("R-2026-10-15") < reports.index("R-2026-10-01")


def test_two_generations_give_the_same_bytes(tmp_path, monkeypatch):
    shutil.copytree(VALID, tmp_path / "tuning")
    monkeypatch.setenv("TUNING_DIR", str(tmp_path / "tuning"))
    readme = tmp_path / "tuning" / "README.md"

    assert tuning_summary.main() == 0
    first = readme.read_bytes()
    assert tuning_summary.main() == 0

    assert readme.read_bytes() == first
    assert first.decode("utf-8").startswith("# Ajuste dos prompts\n")
