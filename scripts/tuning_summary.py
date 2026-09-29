"""Write ``tuning/README.md``: what the channel currently knows, generated
from the tuning records (``TUNING_DIR``) so it never drifts from them.

Every prompt change appears with the text it put in the prompt, its cycle and
what justified it: searching the README for a sentence of a prompt leads to
why it is there. Same records, same bytes.

Usage:
    uv run python scripts/tuning_summary.py
"""

from __future__ import annotations

import sys
from typing import Optional

from src.core.paths import tuning_dir
from src.entities.tuning import (
    PROMPT_FILES,
    Belief,
    Cycle,
    Experiment,
    PromptChange,
    Report,
)
from src.storage import FileTuningRecords, TuningRecords

AREAS = {
    "story_kind": "tipo de história",
    "title_opening": "título e abertura",
    "posting": "publicação",
    "other": "outro",
}
CONFIDENCE = {"low": "baixa", "medium": "média", "high": "alta"}
STATUS = {"lead": "pista", "contested": "contestada", "retired": "aposentada"}
EVENTS = {
    "entered": "entrou",
    "confirmed": "confirmada",
    "weakened": "enfraquecida",
    "overturned": "derrubada",
    "retired": "aposentada",
    "kept_against_evidence": "mantida contra a evidência",
}
KINDS = {"unexplored": "território novo", "variation": "variação", "challenge": "desafio"}
DECISIONS = {"approved": "aprovada", "modified": "modificada", "rejected": "rejeitada"}
JUSTIFICATIONS = {"finding": "achado de", "belief": "crença", "experiment": "experimento"}
ACTIONS = {"keep": "manter", "close": "fechar"}
RESULTS = {
    "helped": "ajudou",
    "hurt": "piorou",
    "unclear": "incerto",
    "not_evaluated": "não avaliado",
}


def _relative(value: Optional[float]) -> str:
    return "—" if value is None else f"{value:.1f}×".replace(".", ",")


def _quote(text: str) -> list[str]:
    return [f"    > {line}".rstrip() for line in text.strip().splitlines()]


def _open_cycle(cycle: Cycle, share: float, since, min_fit: int) -> list[str]:
    deployed = (
        f"implantado em {cycle.deployed}" if cycle.deployed else "ainda não implantado"
    )
    lines = [
        f"Ciclo {cycle.number}, aberto em {cycle.opened}, {deployed}.",
        "",
        "| prompt | versão |",
        "|---|---|",
        *(
            f"| {name} | {f'`{version}`' if (version := getattr(cycle.prompts, name)) else '—'} |"
            for name in PROMPT_FILES
        ),
        "",
    ]
    if share:
        lines.append(
            f"Exploração: {share:.0%} da produção desde {since}, nota mínima {min_fit}."
        )
    else:
        lines.append("Exploração: nenhuma fatia reservada.")
    return lines


def _belief(belief: Belief, show_status: bool) -> list[str]:
    status = f" ({STATUS[belief.status]})" if show_status else ""
    evidence = belief.evidence
    return [
        f"### {belief.id} — {belief.statement}{status}",
        "",
        f"- Sobre: {AREAS[belief.area]}.",
        f"- Evidência: {evidence.videos} vídeos, relativo mediano"
        f" {_relative(evidence.median_relative)}, de {evidence.period.since}"
        f" a {evidence.period.until}.",
        f"- Confiança {CONFIDENCE[belief.confidence]}; último teste em"
        f" {belief.last_tested}; entrou no ciclo {belief.entered.cycle},"
        f" em {belief.entered.date}.",
        "- Histórico:",
        *(
            f"  - {event.date}, ciclo {event.cycle}: {EVENTS[event.event]}"
            f" ({event.source}).{f' {event.note}' if event.note else ''}"
            for event in belief.history
        ),
        "",
    ]


def _beliefs(beliefs: list[Belief], statuses: tuple[str, ...]) -> list[str]:
    chosen = [b for b in beliefs if b.status in statuses]
    if not chosen:
        return ["Nenhuma.", ""]
    show_status = len(statuses) > 1
    return [line for b in chosen for line in _belief(b, show_status)]


def _progress(experiment: Experiment, last: Optional[Report]) -> str:
    if last is None:
        return "- Progresso: nenhum relatório ainda."
    state = next((e for e in last.cycle_state.experiments if e.id == experiment.id), None)
    if state is None:
        return f"- Progresso: não consta no {last.id}."
    return (
        f"- Progresso no {last.id}: {state.settled} de {state.target} vídeos"
        f" assentados, relativo mediano {_relative(state.median_relative)}."
    )


def _experiment(experiment: Experiment, last: Optional[Report]) -> list[str]:
    if experiment.kind == "challenge":
        about = [f"Desafia a crença {experiment.belief}"]
    else:
        about = [KINDS[experiment.kind].capitalize()]
        if experiment.belief:
            about.append(f"sobre a crença {experiment.belief}")
    about.append(
        f"aberto no ciclo {experiment.opened.cycle} em {experiment.opened.date}"
    )
    if experiment.replaces:
        about.append(f"substitui {experiment.replaces}")
    return [
        f"### {experiment.id} — {experiment.question}",
        "",
        f"- {'; '.join(about)}.",
        f"- Por quê: {experiment.motivation}",
        f"- Como reconhecer: {experiment.looks_like}",
        f"- Alvo: {experiment.sample_target} vídeos assentados."
        f" Regra de decisão: {experiment.decision_rule}",
        _progress(experiment, last),
        "",
    ]


def _change(change: PromptChange) -> list[str]:
    decision = DECISIONS[change.decision]
    if change.reason:
        decision += f": {change.reason}"
    reverts = f"; desfaz o ciclo {change.reverts}" if change.reverts else ""
    why = change.justification
    return [
        f"  - `{change.prompt}`, {decision}{reverts} —"
        f" {JUSTIFICATIONS[why.kind]} {why.ref}: {why.summary}",
        "",
        *_quote(change.after),
        "",
    ]


def _cycle(cycle: Cycle) -> list[str]:
    span = (
        f"aberto desde {cycle.opened}"
        if cycle.is_open
        else f"de {cycle.opened} a {cycle.closed}"
    )
    settings = cycle.settings
    lines = [
        f"### Ciclo {cycle.number} — {span}",
        "",
        f"- Implantado em {cycle.deployed}." if cycle.deployed else "- Não implantado.",
        f"- Escrita {settings.writer_model}, avaliação {settings.grader_model},"
        f" renderização {settings.rendering_strategy}.",
    ]
    if cycle.changes:
        lines += ["- Mudanças de prompt:", ""]
        lines += [line for change in cycle.changes for line in _change(change)]
    else:
        baseline = " (linha de base)" if cycle.number == 1 else ""
        lines.append(f"- Mudanças de prompt: nenhuma{baseline}.")
    for change in cycle.outside_changes:
        lines.append(
            f"- Fora da rotina, {change.detected}: `{change.prompt}`"
            f" {change.from_} → {change.to}. {change.reason}"
        )
    for change in cycle.experiment_changes:
        target = f" {change.experiment}" if change.experiment else ""
        note = f" {change.note}" if change.note else ""
        lines.append(
            f"- Experimentos, {change.date}: {change.action}{target} ({change.report}).{note}"
        )
    if cycle.evaluation:
        e = cycle.evaluation
        lines.append(
            f"- Avaliação: {RESULTS[e.result]}; {e.base_videos} vídeos de base,"
            f" relativo mediano {_relative(e.median_relative)} (ciclo anterior"
            f" {_relative(e.previous_median_relative)}).{f' {e.note}' if e.note else ''}"
        )
    if cycle.closing:
        c = cycle.closing
        lines.append(
            f"- Fechamento: recomendação {ACTIONS[c.recommendation]}, decisão"
            f" {ACTIONS[c.decision]}.{f' {c.note}' if c.note else ''}"
        )
    if cycle.reports:
        lines.append(f"- Relatórios: {', '.join(cycle.reports)}.")
    return lines + [""]


def _reports(reports: list[Report]) -> list[str]:
    if not reports:
        return ["Nenhum.", ""]
    return [
        "| relatório | ciclo | período | recomendação | decisão |",
        "|---|---|---|---|---|",
        *(
            f"| {r.id} | {r.cycle} | {r.period.since} a {r.period.until}"
            f" | {ACTIONS[r.recommendation.action]}"
            f" | {ACTIONS[r.decision.action] if r.decision else '—'} |"
            for r in reversed(reports)
        ),
        "",
    ]


def render(records: TuningRecords) -> str:
    plan = records.exploration_plan()
    beliefs = records.beliefs()
    reports = records.reports()
    last = reports[-1] if reports else None
    open_experiments = plan.open()
    queue = [e for e in plan.experiments if e.status == "backlog"]
    lines = [
        "# Ajuste dos prompts",
        "",
        "Gerado por `just tuning-summary` a partir dos arquivos de `tuning/`."
        " Não edite à mão: mude os registros e gere de novo.",
        "",
        "## Ciclo aberto",
        "",
        *_open_cycle(records.open_cycle(), plan.share, plan.share_since, plan.min_fit),
        "",
        "## Base",
        "",
        *_beliefs(beliefs, ("base",)),
        "## O que não funciona",
        "",
        *_beliefs(beliefs, ("does_not_work",)),
        "## Pistas e contestadas",
        "",
        *_beliefs(beliefs, ("lead", "contested", "retired")),
        "## Experimentos abertos",
        "",
        *(
            [line for e in open_experiments for line in _experiment(e, last)]
            or ["Nenhum.", ""]
        ),
        "## Fila de ideias",
        "",
        *(
            [f"- {e.id} — {e.question} Por quê: {e.motivation}" for e in queue]
            or ["Vazia."]
        ),
        "",
        "## Ciclos",
        "",
        *(line for cycle in reversed(records.cycles()) for line in _cycle(cycle)),
        "## Relatórios",
        "",
        *_reports(reports),
    ]
    return "\n".join(lines).rstrip("\n") + "\n"


def main() -> int:
    records = FileTuningRecords(tuning_dir())
    records.write_summary(render(records))
    print(f"{tuning_dir()}/README.md gerado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
