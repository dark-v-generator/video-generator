# Data Model: Ciclo de ajuste dos prompts

**Feature**: 006-prompt-tuning-cycle | **Date**: 2026-09-29

Duas famílias: os **registros de ajuste** (arquivos em `tuning/`, entidades em
`src/entities/tuning.py`) e as **adições ao histórico** (SQLite, entidades em
`src/entities/history.py` e `story_candidate.py`). Chaves e nomes em inglês;
texto livre em português.

## 1. Registros de ajuste

### Experiment

| Campo | Tipo | Regra |
|---|---|---|
| `id` | str | `E` + 3 dígitos, único, nunca reutilizado |
| `status` | `open` \| `closed` \| `backlog` | |
| `kind` | `unexplored` \| `variation` \| `challenge` | |
| `question` | str | a pergunta feita à audiência |
| `motivation` | str | por que vale perguntar |
| `belief` | str \| null | id da crença testada; obrigatório se `kind=challenge` |
| `looks_like` | str | como reconhecer uma história que serve; vai para o prompt de exploração |
| `sample_target` | int > 0 | vídeos assentados necessários |
| `decision_rule` | str | resultado que confirma e resultado que refuta |
| `opened` | `{cycle, date}` \| null | null enquanto `backlog` |
| `replaces` | str \| null | id do experimento que este substitui |
| `outcome` | Outcome \| null | obrigatório se `closed` |

`Outcome`: `verdict` (`confirmed` \| `refuted` \| `inconclusive` \|
`closed_without_verdict` \| `not_testable`), `date`, `cycle`, `videos` (lista de
`record_id`), `settled_count`, `median_relative`, `note`.

Regras: `open` e `closed` exigem todos os campos de texto preenchidos (FR-025);
`backlog` exige só `question` e `motivation`. Mudar um experimento aberto é
fechar o antigo (`closed_without_verdict`) e criar outro com `replaces`
(FR-026). A **ordem na lista é a prioridade**.

Transições: `backlog → open → closed`. `closed` é final. `open → backlog` não
existe: um experimento que já produziu vídeos é fechado.

### ExplorationPlan (`tuning/exploration.yaml`)

| Campo | Tipo | Regra |
|---|---|---|
| `cycle` | int | número do ciclo aberto |
| `share` | float | 0 ≤ share ≤ 0,5 |
| `share_since` | date | data em que a fatia atual passou a valer |
| `min_fit` | int | 0 a 100, padrão 70 |
| `experiments` | list[Experiment] | todos, em ordem de prioridade |

`open()` devolve os `status=open` na ordem do arquivo. É o único arquivo que a
rodada diária lê. Ausente: plano vazio (`share=0`, sem experimentos, `cycle=0`).

### Belief (`tuning/beliefs.yaml`)

| Campo | Tipo | Regra |
|---|---|---|
| `id` | str | `B` + 3 dígitos |
| `statement` | str | |
| `area` | `story_kind` \| `title_opening` \| `posting` \| `other` | |
| `status` | `base` \| `does_not_work` \| `lead` \| `contested` \| `retired` | |
| `evidence` | `{videos, median_relative, period}` | evidência acumulada |
| `confidence` | `low` \| `medium` \| `high` | |
| `entered` | `{cycle, date}` | |
| `last_tested` | date | |
| `history` | list[`{date, cycle, event, source, note}`] | só cresce |

`event`: `entered`, `confirmed`, `weakened`, `overturned`, `retired`,
`kept_against_evidence`. `source` é o id de um relatório ou experimento.

Regras: `base` e `does_not_work` exigem `evidence.videos ≥ 10` (FR-011); abaixo
disso o status é `lead`. Mudança de status sempre acrescenta uma entrada em
`history` (FR-043).

### Cycle (`tuning/cycles/NNN.yaml`)

| Campo | Tipo | Regra |
|---|---|---|
| `number` | int | sequencial, igual ao nome do arquivo |
| `opened` | date | |
| `deployed` | date \| null | quando passou a valer no servidor |
| `closed` | date \| null | null = aberto; exatamente um ciclo aberto |
| `prompts` | `{story, evaluate_story, generate_hashtags, evaluate_exploration}` | fingerprints de 12 hex |
| `settings` | `{writer_model, grader_model, rendering_strategy}` | para saber se mais de uma coisa mudou |
| `changes` | list[PromptChange] | mudanças que **abriram** este ciclo |
| `experiment_changes` | list[`{date, report, action, experiment, note}`] | durante o ciclo |
| `outside_changes` | list[`{detected, prompt, from, to, reason}`] | FR-022 |
| `evaluation` | `{helped \| hurt \| unclear \| not_evaluated, base_videos, median_relative, previous_median_relative, note}` \| null | preenchido no fechamento |
| `reports` | list[str] | ids dos relatórios do ciclo |
| `closing` | `{recommendation, decision, note}` \| null | |

### PromptChange

`prompt`, `before`, `after` (trechos), `justification` (`{kind: finding |
belief | experiment, ref, summary}`), `decision` (`approved` \| `modified` \|
`rejected`), `reason` (obrigatório se `rejected`), `reverts` (número do ciclo
cuja mudança esta desfaz, ou null).

### Report (`tuning/reports/AAAA-MM-DD.yaml`)

| Campo | Tipo |
|---|---|
| `id` | str (`R-AAAA-MM-DD`; um segundo no mesmo dia ganha `-2`) |
| `cycle` | int |
| `period` | `{since, until}` |
| `data_as_of` | datetime da última coleta |
| `videos` | `{considered, excluded: {unsettled, no_snapshot, ambiguous}}` |
| `weekly_reach` | list[`{week, videos, median_views}`] (o `channel.weekly` do pacote; o gráfico da visão de leitura) |
| `distortions` | list[`{kind, note, affects}`] |
| `findings` | list[Finding] |
| `cycle_state` | `{share_intended, share_achieved, unfilled_slots, base_median_relative, experiments: [{id, settled, target, median_relative, days_to_target}]}` |
| `since_previous` | `{previous, new_videos, changed_findings}` |
| `suggestions` | list[`{question, kind, motivation, decision: opened \| backlog \| discarded}`] |
| `recommendation` | `{action: keep \| close, reasons}` |
| `decision` | `{action: keep \| close, note}` |
| `corrects` | str \| null |
| `view_url` | str \| null |

### Finding

`statement`, `area`, `direction` (`works` \| `does_not` \| `inconclusive`),
`videos` (lista de `record_id`), `median_relative`, `confidence`, `is_lead`
(true se menos de 10 vídeos), `belief` (id que reforça ou contraria, ou null),
`unchanged_since` (id do relatório anterior quando os vídeos são os mesmos).

### StoryLabel (`tuning/story_labels.csv`)

`record_id, kind, narrator_acts, title_promise, labelled_at, note`. Uma linha
por vídeo; reclassificação é linha nova com `labelled_at` mais recente, e a
mais recente vale.

## 2. Adições ao histórico

### EvaluatedStory (`src/entities/story_candidate.py`)

| Campo novo | Tipo | Padrão |
|---|---|---|
| `exploration` | `ExplorationFit \| None` | `None` |
| `goal` | str | `"base"` |

`ExplorationFit`: `experiment` (id ou `None` quando nenhum serve), `fit` (0 a
100), `reason`.

### VideoRecord / `video_records`

| Coluna | Tipo | Regra |
|---|---|---|
| `goal` | TEXT | `base` ou id de experimento; NULL nos vídeos anteriores |
| `exploration_experiment` | TEXT | o experimento que a nota apontou, mesmo se o vídeo saiu como base |
| `exploration_fit` | REAL | NULL quando não havia experimento aberto |
| `cycle` | INTEGER | ciclo em vigor na produção; NULL nos anteriores |

### ProductionRecipe

Campos novos: `hashtags_prompt_version` (M1), `exploration_prompt_version` (M4).
Entram em `_RECIPE_COLUMNS` e, portanto, na visão cruzada.

### RunSummary / `run_summaries`

`exploration_slots` (vagas reservadas na rodada) e `exploration_filled`
(vídeos produzidos com objetivo de experimento). Vagas não preenchidas =
diferença.

### Visão cruzada

`CROSSED_COLUMNS` ganha `goal`, `exploration_experiment`, `exploration_fit`,
`cycle`, `hashtags_prompt_version`, `exploration_prompt_version`.

### Migração

Mesmo padrão de `_add_audience_columns`: na abertura, `PRAGMA table_info` e
`ALTER TABLE ... ADD COLUMN` para cada coluna ausente. Sem valor padrão: NULL
significa "antes da feature".

## 3. Relações

```text
Cycle 1 ──< Report
Cycle 1 ──< PromptChange          (as que abriram o ciclo)
Report 1 ──< Finding >── 0..1 Belief
Experiment 0..1 ──> Belief        (a crença testada)
Experiment 0..1 ──> Experiment    (replaces)
VideoRecord.goal ──> "base" | Experiment.id
VideoRecord.cycle ──> Cycle.number
StoryLabel.record_id ──> VideoRecord.id
```

Um experimento atravessa ciclos; seus vídeos são os registros com `goal` igual
ao seu id, em qualquer ciclo.
