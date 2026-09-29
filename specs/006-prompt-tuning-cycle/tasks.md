# Tasks: Ciclo de ajuste dos prompts

**Input**: Design documents from `/specs/006-prompt-tuning-cycle/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: incluídos. O plano exige o golden da rodada inalterado, a aritmética do
relatório feita por código testado e a regra de vagas verificada sem fluxo; cada
gate depende de testes que rodam sem rede e sem modelo.

**Organization**: uma fase por milestone do plano. O milestone é a unidade de merge
(1 PR); as tarefas são commits dentro dele. A ordem segue o plano: primeiro as
histórias P1 (registros, dados, skill), depois a exploração na rodada (P2). A
fundação (entidades e leitura de `tuning/`) entra no PR 1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tarefa aberta)
- **[Story]**: user story do spec (US1..US6)
- Caminhos exatos em cada descrição

## Delivery Plan

| PR | Milestone | Stories | Gate |
|----|-----------|---------|------|
| 1 | M1 — Registros em `tuning/`, verificador e resumo | US6 (base de US1–US3) | `just tuning-check` verde sobre a semente; editar `story.jinja2` faz o check falhar nomeando o prompt e as duas versões; `tuning/README.md` gerado |
| 2 | M2 — Pacote de dados do relatório | US1, US5 | `just tuning-data` sobre 29 ago–28 set em < 10 s, 84 vídeos, relativo de 3 vídeos confere à mão; as duas recusas saem com código 2 |
| 3 | M3 — Skill `/prompt-tuning` e visão de leitura | US1, US2, US3, US5 | primeiro relatório real: registro gravado, visão publicada, recomendação com motivos, `src/prompts/` intocado; fechamento de ensaio deixa `001.yaml` fechado e `002.yaml` aberto com check verde |
| 4 | M4 — Nota de exploração e objetivo no histórico | US4 | golden intocado; com experimento aberto o registro grava `exploration_fit`, `exploration_experiment`, `cycle` e `goal='base'`; banco antigo ganha as colunas sem perder linhas |
| 5 | M5 — Vagas de exploração na rodada diária | US4, US5 | 12 dias com fatia 0,25 e alvo 3 dão 9 de exploração em 36 (±1); dia sem história adequada dá 3 de base e `exploration_filled=0`; golden intocado; `daily_run.py` ≤ 320 linhas |

**Projeção**: 5 PRs.

---

## Phase 1: Setup

- [X] T001 Criar a branch `006-prompt-tuning-cycle` a partir de `main`; levar para ela `specs/006-prompt-tuning-cycle/`, `.specify/feature.json` e a mudança de `AGENTS.md`; registrar a linha de base de `uv run pytest -q` (testes coletados e falhas) e de `wc -l src/flows/daily_run.py` na seção Notes deste arquivo

---

## Phase 2: Fundação (dentro do PR 1)

**Purpose**: entidades dos registros de ajuste e a leitura de `tuning/`. Bloqueia
todas as stories.

- [X] T002 [P] Criar `src/entities/tuning.py` com os modelos pydantic de [data-model.md §1](./data-model.md): `Experiment` (com `Outcome`), `ExplorationPlan` (com `open()` devolvendo os `status=open` na ordem da lista e `ExplorationPlan.empty()` com `share=0`, `cycle=0`), `Belief`, `PromptChange`, `Cycle`, `Finding`, `Report`, `StoryLabel`; validadores para as regras do data-model (`open`/`closed` exigem todos os campos de texto, `closed` exige `outcome`, `challenge` exige `belief`, `share` entre 0 e 0,5, `base`/`does_not_work` exigem `evidence.videos ≥ 10`); sem I/O
- [X] T003 [P] Adicionar `tuning_dir()` em `src/core/paths.py` (lê `TUNING_DIR`, padrão `tuning/`, mesmo padrão de `history_db_path()`)
- [X] T004 Criar `src/storage/tuning_contract.py` com `TuningError` e o Protocol `TuningRecords` de [contracts/tuning-records.md](./contracts/tuning-records.md), e `src/storage/tuning_files.py` com `FileTuningRecords(root: Path)`: lê do disco a cada chamada, `exploration.yaml` ausente devolve o plano vazio, outros arquivos ausentes devolvem lista vazia, arquivo malformado levanta `TuningError` com caminho e campo, `open_cycle()` levanta se não houver exatamente um ciclo aberto, `story_labels()` devolve a linha mais recente por `record_id`, `write_summary()` grava `README.md`; exportar em `src/storage/__init__.py`
- [X] T005 [P] Criar os fixtures `tests/fixtures/tuning/valid/` (um ciclo fechado, um aberto, duas crenças, um experimento aberto, um fechado com `outcome`, um em `backlog`, dois relatórios, rótulos com uma reclassificação) e um diretório `tests/fixtures/tuning/broken-<regra>/` para cada invariante 2 a 7 de [contracts/tuning-records.md](./contracts/tuning-records.md), cada um quebrando só aquela regra
- [X] T006 Criar `tests/storage/test_tuning_files.py`: carga completa de `valid/`, ordem de prioridade preservada em `open()`, plano vazio sem arquivo, `TuningError` nomeando caminho e campo em YAML inválido, rótulo mais recente vence, `write_summary` grava o arquivo

---

## Phase 3: Milestone 1 — Registros, verificador e resumo (US6) — PR 1

**Goal**: o conhecimento do canal existe em arquivos versionados, validados por
um comando, com um resumo legível gerado a partir deles.

**Independent test criteria**:

- `just tuning-check` sai com código 0 sobre a semente e lista cada verificação.
- Uma linha acrescentada a `src/prompts/story.jinja2` faz o check sair com código 1, dizendo que `story` mudou fora da rotina, com a versão registrada e a do disco.
- `tuning/README.md` mostra o ciclo 1 aberto, as crenças de setembro como pistas e nenhum experimento, e é idêntico em duas gerações seguidas.

### Tests

- [X] T007 [P] [US6] Criar `tests/scripts/test_tuning_check.py`: `valid/` passa; cada `broken-<regra>/` falha com mensagem que nomeia a regra; fingerprint divergente falha e deixa de falhar quando a mudança consta em `outside_changes`; relatório antigo modificado em relação ao `HEAD` falha (repositório git temporário em `tmp_path`)
- [X] T008 [P] [US6] Criar `tests/scripts/test_tuning_summary.py`: README gerado de `valid/` contém as seções na ordem do contrato, cada crença com evidência, confiança, último teste e histórico, cada mudança de prompt com trecho `after`, ciclo e justificativa; duas gerações dão bytes iguais
- [X] T009 [P] [US6] Estender `tests/test_container_config.py` e `tests/entities/` para `hashtags_prompt_version`: a receita traz o fingerprint de `generate_hashtags.jinja2` e a coluna aparece em `CROSSED_COLUMNS`

### Implementation

- [X] T010 [US6] Adicionar `hashtags_prompt_version` a `ProductionRecipe` em `src/entities/history.py` e a `build_production_recipe` em `src/core/recipe.py`; adicionar a coluna a `src/storage/sqlite_history.py` pelo padrão de `_add_audience_columns` (`ALTER TABLE video_records ADD COLUMN` quando ausente) e a `tests/fakes/memory_history.py`
- [X] T011 [US6] Criar `scripts/tuning_check.py` com as nove verificações de [contracts/tuning-records.md](./contracts/tuning-records.md): uma linha por verificação, código 0 ou 1, a verificação 8 comparando `prompts.fingerprint` com o ciclo aberto, a 9 usando `git diff --name-only HEAD -- tuning/reports tuning/cycles` e ignorando arquivos novos e o ciclo aberto
- [X] T012 [US6] Criar `scripts/tuning_summary.py`, que gera `tuning/README.md` via `TuningRecords.write_summary` com as seções e a ordem do contrato, saída determinística
- [X] T013 [US6] Adicionar as receitas `tuning-check` e `tuning-summary` ao `Justfile`, com comentário de uso no padrão das receitas existentes
- [X] T014 [US6] Criar a semente em `tuning/`: `cycles/001.yaml` aberto com os fingerprints reais de `story`, `evaluate_story` e `generate_hashtags` (`evaluate_exploration: null`), `settings` lidos de `config.prod.yaml`, `changes: []`; `exploration.yaml` com `cycle: 1`, `share: 0.25`, `min_fit: 70`, `experiments: []`; `story_labels.csv` só com o cabeçalho; `reports/` vazio com `.gitkeep`
- [X] T015 [US6] Criar `tuning/beliefs.yaml` com os achados do relatório de setembro (84 vídeos, 29 ago–28 set), cada um com `status: lead`, `evidence` com a contagem do relatório, `confidence: low` e a entrada `entered` em `history` apontando para o relatório de setembro: histórias de trabalho em que o narrador dá o troco, conflitos com sogros, títulos que prometem reação, títulos de 90 a 120 caracteres, watch médio ≥ 35 s, desconhecidos e empresas, luto sem vilão nem virada, histórias de casal, postagens de sexta
- [X] T016 [US6] Rodar `just tuning-summary` e versionar o `tuning/README.md` gerado

### Live verification (milestone gate)

- [X] T017 [US6] Executar [quickstart §1](./quickstart.md): suíte verde, `just tuning-check` verde, check falhando com `story.jinja2` editado e voltando a passar depois de `git checkout`; anotar as saídas em Notes

**Checkpoint**: Milestone 1 DONE ✅ (2026-09-29)

---

## Phase 4: Milestone 2 — Pacote de dados do relatório (US1, US5) — PR 2

**Goal**: um comando entrega todos os números de um relatório, já calculados, e
recusa quando os dados não sustentam achados.

**Independent test criteria**:

- `just tuning-data --since 2026-08-29 --until 2026-09-28` termina em menos de 10 s e considera os 84 vídeos do relatório de setembro.
- O `relative` de três vídeos escolhidos confere com a conta manual sobre `just report --csv`.
- `--days 3` e `--max-age-days 0` saem com código 2 e uma linha dizendo o que fazer.

### Tests

- [X] T018 [P] [US1] Criar `tests/capabilities/test_tuning_relative.py`: relativo com 5 vizinhos de cada lado, nas bordas do período (10 de um lado só), com menos de 5 vizinhos (`None`), empate de horário, vídeo sem snapshot fora da vizinhança, o próprio vídeo excluído, assentado calculado contra a data da coleta e não contra hoje
- [X] T019 [P] [US1] Criar `tests/capabilities/test_tuning_periods.py`: mediana semanal do canal, semana sem vídeos, contagem de tentativas falhas e de registros sem tentativa bem-sucedida
- [X] T020 [P] [US5] Criar `tests/capabilities/test_tuning_progress.py`: comparação entre ciclos só com vídeos de base assentados, `goal` NULL tratado como base, `previous.cycle = 0` para o que veio antes do ciclo 1, `also_changed` preenchido quando modelo ou estratégia diferem, `verdict_possible` falso abaixo de 20 de cada lado; progresso por experimento com `days_to_target` e `None` sem produção; fatia atingida desde `share_since`
- [X] T021 [P] [US1] Criar `tests/scripts/test_tuning_data.py`: pacote com todas as chaves do contrato sobre um SQLite semeado em `tmp_path`, `unlabelled` listando os ids sem rótulo, `prompt_drift` preenchido, as duas recusas com código 2 e stdout vazio, `--json` gravando o mesmo conteúdo

### Implementation

- [X] T022 [P] [US1] Criar `src/capabilities/tuning/__init__.py` e `src/capabilities/tuning/relative.py`: `settled(row, data_as_of, settle_days)` e `relative_performance(rows, settle_days)` conforme [research.md §5](./research.md), puras sobre `CrossedRow`
- [X] T023 [P] [US1] Criar `src/capabilities/tuning/periods.py`: `weekly_channel(rows)` e `lost_uploads(rows)`
- [X] T024 [P] [US5] Criar `src/capabilities/tuning/cycles.py`: `compare_cycles(rows, cycles, minimum=20)` devolvendo `current`, `previous`, `also_changed`, `verdict_possible` e `reason`
- [X] T025 [P] [US5] Criar `src/capabilities/tuning/progress.py`: `experiment_progress(rows, plan, today)` e `share_achieved(rows, plan)`
- [X] T026 [US1] Criar `scripts/tuning_data.py` com os argumentos e o formato de [contracts/tuning-data.md](./contracts/tuning-data.md): lê `SqliteHistoryStore(history_db_path()).crossed_view(...)` e `FileTuningRecords(tuning_dir())`, aplica as recusas antes de qualquer saída, junta os rótulos às linhas, serializa em JSON
- [X] T027 [US1] Adicionar a receita `tuning-data *args` ao `Justfile`

### Live verification (milestone gate)

- [X] T028 [US1] Executar [quickstart §2](./quickstart.md) sobre o histórico real depois de `just sync-history`: tempo, contagem de 84, conferência manual de três vídeos, as duas recusas; anotar os três `record_id` e os valores em Notes

**Checkpoint**: Milestone 2 DONE ✅ (2026-09-29)

---

## Phase 5: Milestone 3 — Skill `/prompt-tuning` e visão de leitura (US1, US2, US3, US5) — PR 3

**Goal**: o operador pede um relatório, lê em uma página, recebe a recomendação
de manter ou fechar o ciclo e, se fechar, ajusta os prompts com o motivo
registrado.

**Independent test criteria**:

- `/prompt-tuning` grava um arquivo em `tuning/reports/`, publica a página e termina com recomendação e motivos; `git status --short src/prompts/` fica vazio.
- Todo achado do relatório tem `videos`, `median_relative` e `confidence`; achado com menos de 10 vídeos tem `is_lead: true`.
- `/prompt-tuning close` com uma mudança aprovada e outra rejeitada altera só o prompt da aprovada, fecha `001.yaml`, abre `002.yaml` com os fingerprints novos, e `just tuning-check` passa.
- Tudo o que a página mostra está no YAML do relatório.

### Implementation

- [X] T029 [P] [US1] Criar `.claude/skills/prompt-tuning/references/records.md`: formato de cada arquivo de `tuning/` com um exemplo, regras de id, e as categorias de rótulo (`kind`, `narrator_acts`, `title_promise`) tiradas do relatório de setembro, com a instrução de registrar categoria nova no relatório em que aparece
- [X] T030 [P] [US2] Criar `.claude/skills/prompt-tuning/references/recommendation.md`: critérios para recomendar fechar ou manter de [contracts/skill.md](./contracts/skill.md), os limites de [research.md §13](./research.md) e o motivo de cada um, a regra de que pista não justifica mudança de base, como ligar distorções do período aos achados, quando um achado recebe `unchanged_since`
- [X] T031 [P] [US1] Criar `.claude/skills/prompt-tuning/references/reading-view.md`: as nove seções da página na ordem do contrato, o que cada uma tira do YAML do relatório, a regra de republicar no `view_url` do relatório anterior, página privada
- [X] T032 [US1] Criar `.claude/skills/prompt-tuning/SKILL.md` com frontmatter (`name`, `description`, `argument-hint`) e o fluxo do relatório, passos 1 a 13 de [contracts/skill.md](./contracts/skill.md), escrito como racional (o que cada passo protege), em português, com as três formas de invocação e a regra de que sem `close` a skill não toca em `src/prompts/` nem em `tuning/cycles/`
- [X] T033 [US5] Acrescentar a `.claude/skills/prompt-tuning/SKILL.md` a seção de experimentos: progresso e recomendação por experimento, veredito contra a `decision_rule` quando o alvo é atingido, recomendação de quantos manter e em que ordem com o tempo de cada um, gravação em `exploration.yaml` e em `experiment_changes`, `share_since` atualizado ao mudar a fatia, experimento incompleto vai para `backlog`, ao menos duas sugestões por relatório sendo uma território novo ou desafio, aviso de que as vagas só existem depois do M5
- [X] T034 [US3] Acrescentar a `.claude/skills/prompt-tuning/SKILL.md` a seção de fechamento, passos 1 a 9 de [contracts/skill.md](./contracts/skill.md): vereditos, avaliação do ciclo, atualização de `beliefs.yaml` com entrada em `history`, proposta de cada mudança com redação atual, proposta e justificativa, aprovação individual, reversão do que piorou, criação do ciclo seguinte, `just tuning-check`, `just tuning-summary`, `uv run pytest tests/prompts -q`, lembrete de commit e `just deploy`; a skill não faz commit nem deploy; mudanças de prompt escritas como razão, nunca como regra casuística
- [X] T035 [US2] Acrescentar a `.claude/skills/prompt-tuning/SKILL.md` o tratamento de mudança de prompt fora da rotina (perguntar o motivo, gravar em `outside_changes`, recomendar fechar), o primeiro uso, e `/prompt-tuning view AAAA-MM-DD` para refazer a página a partir do registro
- [X] T036 [P] [US1] Criar `docs/tuning.md` para o operador: o que é ciclo e o que é relatório, quando pedir, o que decidir, o que exige `just deploy`, onde fica cada registro; acrescentar ao `README.md` uma seção curta apontando para ele

### Live verification (milestone gate)

- [X] T037 [US1] Executar a primeira parte de [quickstart §3](./quickstart.md) em um branch descartável: `/prompt-tuning`, conferir rótulos, registro, link da página e recomendação; `just tuning-check` verde e `git status --short src/prompts/` vazio; medir o tempo do operador (alvo: menos de 10 minutos)
- [X] T038 [US3] Executar a segunda parte de [quickstart §3](./quickstart.md): `/prompt-tuning close` aprovando uma mudança e rejeitando outra; conferir `001.yaml` fechado, `002.yaml` aberto, diff só no prompt aprovado, check verde; medir o tempo (alvo: menos de 45 minutos); apagar o branch de ensaio e anotar em Notes o que a skill precisou de ajuste

**Checkpoint**: Milestone 3 DONE ✅ (2026-09-29)

---

## Phase 6: Milestone 4 — Nota de exploração e objetivo no histórico (US4) — PR 4

**Goal**: com experimento aberto, toda história avaliada recebe a segunda nota, e
todo vídeo registra objetivo, as duas notas e o ciclo. A seleção ainda não muda.

**Independent test criteria**:

- Sem experimento aberto, nenhuma chamada a `evaluate_exploration` acontece e o golden não muda.
- Com experimento aberto, `just daily-generate 1` grava `exploration_experiment`, `exploration_fit`, `cycle` e `exploration_prompt_version`, com `goal='base'`.
- Um `history.sqlite` criado antes do PR abre, ganha as colunas e mantém a contagem de linhas.
- Mudar o texto de um experimento não muda nenhum fingerprint de prompt.

### Tests

- [ ] T039 [P] [US4] Estender `tests/capabilities/test_discovery.py`: sem experimentos o resultado e o número de chamadas ao LLM são os atuais; com experimentos toda avaliada que não é `Erro` recebe `exploration`; história abaixo de "Boa" com `fit ≥ min_fit` entra no fim da lista; nenhuma história duplicada; falha de `evaluate_exploration` propaga
- [ ] T040 [P] [US4] Estender `tests/storage/test_sqlite_history.py` (parametrizado sobre SQLite e memória): os quatro campos novos gravam e voltam; banco criado com o esquema anterior ganha as colunas e mantém as linhas com NULL; `goal_counts(since)` conta total e exploração e ignora `imported`; colunas novas aceitas por `crossed_view` em `--sort` e `--filter`
- [ ] T041 [P] [US4] Criar `tests/proxies/test_evaluate_exploration.py`: normalização da resposta, id fora da lista recebida levanta nomeando o id, `fit` fora de 0–100 levanta, `experiment: null` dá `fit` 0; e em `tests/prompts/test_loader.py` que o template renderiza com uma lista de experimentos e que o fingerprint não muda quando a lista muda
- [ ] T042 [P] [US4] Estender `tests/flows/test_daily_run_history.py`: registro com os campos de exploração copiados da candidata e `cycle` do plano; sem plano os campos ficam `None` e `goal="base"`

### Implementation

- [ ] T043 [P] [US4] Criar `src/prompts/evaluate_exploration.jinja2` conforme [contracts/exploration.md](./contracts/exploration.md): racional (o canal reserva produção para aprender; a nota mede se a história é um teste justo de uma pergunta; não mede se vai bem; novidade sozinha não vale), lista de experimentos por `id`, `question` e `looks_like`, saída JSON `{experiment, fit, reason}`, sem CAPS de ênfase
- [ ] T044 [P] [US4] Adicionar `ExplorationFit` e os campos `exploration` e `goal` a `EvaluatedStory` em `src/entities/story_candidate.py`
- [ ] T045 [US4] Adicionar `evaluate_exploration(title, content, experiments, target_language) -> dict` a `src/proxies/interfaces.py` e implementar em `src/proxies/llm_prompt_proxy.py`, `src/proxies/llm_dspy_proxy.py` e `src/proxies/mock_llm_proxy.py`, com a normalização do contrato; no `FakeLLMProxy` de `tests/fakes/proxies.py`, resultado programável por título
- [ ] T046 [US4] Em `src/capabilities/discovery/contract.py` e `src/capabilities/discovery/reddit_discovery.py`, adicionar `experiments` e `min_fit` a `find_best_stories` com o comportamento de [contracts/exploration.md](./contracts/exploration.md); acompanhar no `FakeDiscovery` de `tests/flows/test_daily_run.py`
- [ ] T047 [US4] Em `src/entities/history.py`, adicionar `goal`, `exploration_experiment`, `exploration_fit` e `cycle` a `VideoRecord`, `exploration_prompt_version` a `ProductionRecipe`, e as colunas a `CROSSED_COLUMNS`; em `src/core/recipe.py`, o fingerprint de `evaluate_exploration.jinja2`
- [ ] T048 [US4] Em `src/storage/history_contract.py`, adicionar `goal_counts(since) -> GoalCounts`; em `src/storage/sqlite_history.py`, as colunas por migração idempotente, a gravação e a leitura dos campos, `goal_counts` e o mapeamento em `_CROSSED_SQL`; em `tests/fakes/memory_history.py`, o mesmo
- [ ] T049 [US4] Em `src/flows/run_record.py`, preencher em `video(...)` os campos de exploração a partir da candidata e `cycle` a partir do plano recebido na construção do `RunRecord`; em `src/core/container.py`, passar o plano lido por `FileTuningRecords(tuning_dir())`
- [ ] T050 [US4] Em `scripts/performance_report.py`, acrescentar a coluna `objetivo` à `TABLE`; atualizar `tuning/cycles/001.yaml` com o fingerprint de `evaluate_exploration` e rodar `just tuning-check`

### Live verification (milestone gate)

- [ ] T051 [US4] Executar [quickstart §4](./quickstart.md): suíte e golden, migração sobre uma cópia do banco real, `just daily-generate 1` com `TUNING_DIR` temporário e experimento aberto; conferir em `just tuning-data` que a seção `exploration.experiments` aparece; anotar as saídas em Notes

**Checkpoint**: Milestone 4 DONE

---

## Phase 7: Milestone 5 — Vagas de exploração na rodada diária (US4, US5) — PR 5

**Goal**: a rodada reserva a fatia de exploração, entrega cada vaga ao experimento
de maior prioridade com história adequada e conta as vagas que ficaram vazias.

**Independent test criteria**:

- Doze dias simulados com fatia 0,25 e alvo 3 produzem 9 vídeos de exploração em 36 (±1), no máximo 1 por dia.
- Um dia sem história adequada produz 3 vídeos de base, com `exploration_slots ≥ 1` e `exploration_filled = 0`.
- Com dois experimentos abertos e história para os dois, a vaga vai para o primeiro do arquivo.
- Sem experimento aberto, as mensagens de progresso e o golden são idênticos aos de hoje.
- `wc -l src/flows/daily_run.py` ≤ 320.

### Tests

- [ ] T052 [P] [US4] Criar `tests/capabilities/test_exploration_allocation.py`: `slots_due` na sequência 1, 1, 0, 1 com fatia 0,25 e alvo 3, recuperação depois de um dia vazio respeitando o teto diário, zero com `share=0` ou sem experimento aberto; `arrange` com prioridade entre experimentos, experimento prioritário sem história, história boa de base que serve a um experimento ocupando só a vaga de exploração, candidatas que entraram só pela exploração e não foram escolhidas ficando de fora, vagas devolvidas mesmo sem escolhidas
- [ ] T053 [P] [US4] Criar `tests/fakes/exploration.py` com `FakeExplorationSource(plan)` e `tests/flows/test_daily_run_exploration.py`: vídeo de exploração com `goal` igual ao id; história de exploração que falha na escrita substituída por uma de base com a vaga contada como não preenchida; resumo da rodada com `exploration_slots` e `exploration_filled`; mensagem de fim de busca com " (N de exploração)" só quando `slots > 0`; publish-only sem leitura do plano
- [ ] T054 [P] [US5] Estender `tests/storage/test_sqlite_history.py` para `exploration_slots` e `exploration_filled` em `RunSummary`, inclusive a migração de `run_summaries`

### Implementation

- [ ] T055 [P] [US4] Criar `src/capabilities/exploration/__init__.py`, `src/capabilities/exploration/contract.py` (`ExplorationSource`, `GoalCounts`) e `src/capabilities/exploration/allocation.py` (`slots_due`, `arrange`) conforme [contracts/exploration.md](./contracts/exploration.md) e [research.md §6 e §7](./research.md); mover `GoalCounts` de onde foi criado no M4 para `contract.py`, se for o caso
- [ ] T056 [US5] Adicionar `exploration_slots` e `exploration_filled` a `RunSummary` em `src/entities/history.py`, às colunas de `run_summaries` em `src/storage/sqlite_history.py` (migração idempotente) e a `tests/fakes/memory_history.py`; em `src/flows/run_record.py`, `found(candidates, target, exploration_slots=0)` e o cálculo de `exploration_filled` em `finish()`
- [ ] T057 [US4] Em `src/flows/daily_run.py`, adicionar o campo `exploration: ExplorationSource` e, em `_find`, ler o plano, passar `experiments` e `min_fit` à descoberta, chamar `arrange` e `record.found(..., exploration_slots=slots)`; manter o arquivo em até 320 linhas, movendo a montagem da mensagem de fim de busca para `src/flows/run_record.py` se for preciso
- [ ] T058 [US4] Em `src/core/container.py`, adicionar o provider `exploration_source` como Factory sobre `FileTuningRecords` (expondo `plan()`), e passá-lo a `DailyRun`; cobrir em `tests/test_container_config.py` que `TUNING_DIR` é lido a cada rodada
- [ ] T059 [P] [US4] Atualizar `docs/architecture.md` (capacidades `exploration` e `tuning`, o que a rodada lê de `tuning/`), `docs/configuration.md` (`TUNING_DIR`) e `docs/tuning.md` (como as vagas são distribuídas, o que é vaga não preenchida); remover de `.claude/skills/prompt-tuning/SKILL.md` o aviso de que as vagas só existem depois do M5

### Live verification (milestone gate)

- [ ] T060 [US4] Executar a primeira parte de [quickstart §5](./quickstart.md): testes de alocação e de fluxo, golden intocado, `wc -l src/flows/daily_run.py`
- [ ] T061 [US4] Executar a parte do servidor de [quickstart §5](./quickstart.md): abrir um experimento pela skill, `just deploy`, e depois das duas rodadas seguintes conferir `goal` em `just report` e as vagas em `run_summaries`; anotar em Notes o que saiu

**Checkpoint**: Milestone 5 DONE

---

## Phase 8: Polish

- [ ] T062 [P] Rodar a verificação final de [quickstart.md](./quickstart.md): suíte inteira, `grep -rn "tuning/" src/` só em `src/core/paths.py`, `grep -rn "yaml" src/flows/` vazio
- [ ] T063 [P] Atualizar `specs/006-prompt-tuning-cycle/checklists/requirements.md`: substituir as notas do primeiro rascunho pelas decisões da sessão de clarificação
- [ ] T064 Depois de quatro semanas de uso, conferir SC-008 (fatia atingida a até 10 pontos da pretendida) e SC-006 (duas sugestões por relatório) sobre os relatórios gravados, e registrar o resultado em `docs/tuning.md`

---

## Dependencies & Execution Order

### Milestones

```text
Setup → Fundação → M1 → M2 → M3 → M4 → M5 → Polish
```

- **M2** depende de M1 (lê ciclos, plano e rótulos).
- **M3** depende de M2 (a skill não calcula; lê o pacote) e de M1 (check e resumo).
- **M4** depende de M1 (plano e ciclo) e estende o pacote do M2.
- **M5** depende de M4 (nota de exploração e `goal_counts`).
- M4 não depende de M3 em código, mas o gate de M5 no servidor usa a skill para abrir o experimento.

Um milestone só começa depois que o gate do anterior passa.

### User stories

| Story | Completa em | Depende de |
|---|---|---|
| US6 — conhecimento em um lugar | M1 | fundação |
| US1 — relatório de acompanhamento | M3 | M1, M2 |
| US2 — decidir quando o ciclo termina | M3 | US1 |
| US3 — ajustar os prompts com o motivo | M3 | US2 |
| US5 — assentar um ciclo | M3 (vereditos e comparação), M5 (fatia atingida) | US1; M4 para os dados de experimento |
| US4 — espaço para explorar | M5 | M3 para escrever experimentos, M4 para a nota |

### Dentro de cada milestone

- Testes primeiro, falhando, depois a implementação.
- Entidades antes de armazenamento, armazenamento antes de scripts e fluxo.
- A verificação ao vivo fecha o milestone.

### Parallel opportunities

- Fundação: T002, T003 e T005 em paralelo; T004 depois de T002 e T003; T006 depois de T004 e T005.
- M1: T007, T008 e T009 em paralelo; T011 e T012 em arquivos diferentes, depois de T010.
- M2: os quatro testes (T018–T021) em paralelo; os quatro módulos (T022–T025) em paralelo; T026 depois deles.
- M3: as três referências (T029–T031) e `docs/tuning.md` (T036) em paralelo; T032 a T035 em sequência, porque editam o mesmo `SKILL.md`.
- M4: os quatro testes (T039–T042) em paralelo; T043 e T044 em paralelo; T045 a T050 em sequência.
- M5: os três testes (T052–T054) em paralelo; T055 e T059 em paralelo com o resto; T056, T057 e T058 em sequência.

---

## Parallel Example: Milestone 2

```bash
# Testes do M2, juntos:
Task: "tests/capabilities/test_tuning_relative.py"
Task: "tests/capabilities/test_tuning_periods.py"
Task: "tests/capabilities/test_tuning_progress.py"
Task: "tests/scripts/test_tuning_data.py"

# Módulos puros do M2, juntos:
Task: "src/capabilities/tuning/relative.py"
Task: "src/capabilities/tuning/periods.py"
Task: "src/capabilities/tuning/cycles.py"
Task: "src/capabilities/tuning/progress.py"
```

---

## Implementation Strategy

### MVP: até o Milestone 3

1. Setup e fundação.
2. M1: o conhecimento do canal está gravado e validado.
3. M2: os números do relatório saem de um comando.
4. M3: `/prompt-tuning` entrega relatório, recomendação e ajuste de prompts.
5. **Parar e validar**: usar a rotina por uma ou duas semanas. As três histórias P1 estão completas aqui, e nada na rodada diária mudou.

### Depois do MVP

6. M4: a segunda nota começa a ser gravada, sem mudar a seleção. Serve para ver, antes de reservar vagas, quantas histórias por dia servem a cada experimento.
7. M5: as vagas passam a existir.

Se os dados do M4 mostrarem que quase nenhuma história atinge `min_fit`, ajustar o `looks_like` dos experimentos ou o `min_fit` antes de implantar o M5.

---

## Notes

- [P] = arquivos diferentes, sem dependência de tarefa aberta.
- O golden (`tests/fixtures/daily_run_golden.json`) não muda em nenhum PR.
- A skill escreve os registros de `tuning/`; o código só os lê, com exceção do `README.md` gerado.
- Commit por tarefa ou grupo lógico; mensagens de commit em inglês.
- Linha de base (T001, 2026-09-29, `main` em 9812b37): `uv run pytest -q` → 494 passed, 0 falhas; `wc -l src/flows/daily_run.py` → 315.
- Gate M1 (T017, 2026-09-29, branch `006-prompt-tuning-cycle`):
  - `uv run pytest -q` → 537 passed (linha de base 494 + 43 novos), 0 falhas.
  - `uv run pytest tests/storage/test_tuning_files.py tests/scripts/test_tuning_check.py tests/scripts/test_tuning_summary.py -q` → 38 passed.
  - `just tuning-check` sobre a semente → nove linhas `ok`, "tudo certo", saída 0.
  - `just tuning-summary` duas vezes → `git diff --stat tuning/README.md` vazio. README: ciclo 1 aberto, nove crenças de setembro em "Pistas e contestadas", "Experimentos abertos: Nenhum".
  - `{# quickstart #}` na primeira linha de `src/prompts/story.jinja2` → `FALHOU 8. ... prompt story mudou fora da rotina: 42072ca8893c → 4ba6834641b4`, saída 1; depois de `git checkout src/prompts/story.jinja2`, saída 0.
  - Migração sobre uma cópia de `.storage/history.sqlite`: 444 linhas mantidas, coluna `hashtags_prompt_version` criada, NULL em todas.
  - Semente: `cycles/001.yaml` com `deployed: null`, porque `tuning/` ainda não foi implantado; preencher no próximo `just deploy`. Nenhum registro do histórico tem receita ainda (os 444 são importados), então não havia versão implantada a conferir.
  - Contagem de B005 (≥ 35 s, 30 vídeos) refeita sobre o histórico local; o relatório de setembro não a trazia.
- Gate M2 (T028, 2026-09-29, branch `006-m2-tuning-data`, depois de `just sync-history`: 447 registros, última coleta 2026-09-28 16:28 local):
  - `uv run pytest -q` → 571 passed (M1 537 + 34 novos), 0 falhas. `uv run pytest tests/capabilities/test_tuning_relative.py tests/capabilities/test_tuning_periods.py tests/capabilities/test_tuning_progress.py tests/scripts/test_tuning_data.py -q` → 34 passed.
  - `time just tuning-data --since 2026-08-29 --until 2026-09-28 --json …/pack.json` → 0,53 s, saída 0. 116 registros no período; os 84 do relatório de setembro são os que têm snapshot: `considered` 64 + `unsettled` 20; `no_snapshot` 32 (uploads que não chegaram ao TikTok: `never_published` 30, `attempts_failed` 35). Medianas semanais 1 065 (31 ago) → 930 → 602 → 430 (21 set), as do relatório de setembro. `prompt_drift` vazio; `cycle_comparison` ciclo 1 com 0 vídeos contra ciclo 0 com 64, `verdict_possible: false`.
  - Conferência à mão sobre `just report --csv` (todo o histórico; assentado = `latest_taken_at − last_scheduled_at ≥ 7 d`, 64 vídeos, mesma contagem do pacote), 5 vizinhos de cada lado ordenados por horário: 335 → 1024 / mediana 1020 = 1,00 (pacote 1,0); 364 → 918 / 984,5 = 0,93 (pacote 0,93); 405 → 273 / 534 = 0,51 (pacote 0,51, vizinhos pulando 400 e 409, não assentados).
  - `just tuning-data --days 3` → saída 2, stdout vazio, "0 vídeos assentados no período; o mínimo é 30; amplie com `--days`". `just tuning-data --max-age-days 0` → saída 2, stdout vazio, "última coleta em 2026-09-28; rode `just prod-collect-performance`".
  - `just tuning-check` → "tudo certo" (a verificação 8 passou a usar o mesmo `prompt_drift` do pacote).
  - Decisões de implementação: o relativo e os ciclos usam o histórico inteiro, não só o período (os vizinhos de um vídeo na borda do período e os vídeos do ciclo anterior ficam fora dele); o assentado conta até a coleta do próprio vídeo; `published_at` é o `scheduled_at` da tentativa agendada mais recente, senão o `tiktok_created_at` do snapshot (5 vídeos no histórico tinham falha no publicador e estão no TikTok); vídeo sem `cycle` gravado pertence ao ciclo mais recente implantado até o dia em que foi feito (0 antes do primeiro), para que os vídeos entre o deploy do ciclo 1 e o do M4 não caiam no ciclo 0; `never_published` conta os registros sem tentativa agendada e sem nada no TikTok; `exploration.experiments` já traz os experimentos abertos (com `produced: 0` até o M4 gravar `goal`), em vez de lista vazia.
- Gate M3 (T037–T038, 2026-09-29, branch `006-m3-prompt-tuning-skill`, ensaio em `tuning-rehearsal`):
  - `uv run pytest -q` → 572 passed (M2 571 + 1 novo), 0 falhas; golden sem diff.
  - T037, `/prompt-tuning` sobre 31 ago–29 set (coleta de 28 set): check verde; `deployed` do ciclo 1 perguntado ao operador ("ainda não", fica `null`); `tuning-data` com 113 vídeos, 59 assentados; 113 rótulos acrescentados a `story_labels.csv` (11 com nota de dúvida), `unlabelled` vazio na segunda rodada; 11 achados (6 com 10 ou mais vídeos, 5 pistas), 4 distorções, 3 sugestões (variação, desafio, território novo); recomendação `keep` com 3 motivos. `tuning/reports/2026-09-29.yaml` gravado e listado no ciclo 1, check verde; página privada publicada em https://claude.ai/artifact/5dHyYv2yjZcVHKUUTr31hN e republicada com a decisão; decisão do operador `keep`, sugestões para a fila como E001–E003 (`backlog`, `moved_to_backlog` no ciclo 1); `tuning-summary` com o relatório e a fila; `git status --short src/prompts/` vazio. Tempo do operador: duas perguntas (deploy, decisão) e a leitura, bem abaixo de 10 minutos; o trabalho da skill levou cerca de 20 minutos de relógio.
  - T038, fechamento de ensaio contra a recomendação: relatório `R-2026-09-29-2` sobre os mesmos dados, com os 11 achados em `unchanged_since: R-2026-09-29` e `new_videos: 0`; ciclo 1 fechado com `evaluation.result: not_evaluated`; B001 e B003 com entrada `weakened`; duas propostas em `story.jinja2`, uma aprovada (comprimento do título, achado de 26 vídeos) e uma rejeitada com motivo (tempo assistido é resultado, não causa); `cycles/002.yaml` aberto com o fingerprint novo de `story` (42072ca8893c → 85381e3c6bed) e as duas mudanças em `changes`; `exploration.yaml` no ciclo 2; `tuning-check` verde, `tuning-summary` mostra o trecho aprovado com ciclo e achado, `uv run pytest tests/prompts -q` → 10 passed; `git diff --stat src/prompts/` → só `story.jinja2`, 1 linha. Depois do commit, editar `cycles/001.yaml` faz a verificação 9 falhar ("já estava fechado e mudou"). Tempo do operador: três respostas, poucos minutos.
  - Ajustes que o ensaio pediu, já na skill: (1) `scripts/group.py` dentro da skill, para que a contagem e a mediana de cada achado saiam de um comando e não da leitura das linhas; (2) `Report.weekly_reach` e `ExperimentState.days_to_target` nas entidades, porque a página mostra o gráfico semanal e a previsão e tudo o que ela mostra precisa estar no registro; (3) a skill avisa antes de fechar um ciclo com menos de 20 vídeos de base, porque `compare_cycles` só compara com o ciclo imediatamente anterior e a mudança seguinte ficaria sem veredito para sempre (pergunta do operador no ensaio); (4) a skill prefere poucas mudanças por ciclo e diz que duas no mesmo ciclo não se separam.
  - Interpretação do contrato: "sem `close` a skill não toca em `tuning/cycles/`" virou "não abre nem fecha ciclo e não muda `prompts`"; no ciclo aberto, o relatório acrescenta a `reports`, `experiment_changes` e `outside_changes` e preenche `deployed`, porque a verificação 6 exige o relatório na lista do ciclo e o data-model põe as mudanças de experimento e as de fora da rotina no ciclo.
  - Não verificado: a mudança de prompt fora da rotina de ponta a ponta pela skill (coberta pelo teste da verificação 8 no M1), a recusa do pacote dentro da skill, e `/prompt-tuning view`.
  - Ponto em aberto para decidir: o relativo compara cada vídeo com vizinhos quase sempre do mesmo ciclo, então uma melhora que atinge todos os vídeos de um ciclo por igual quase não aparece em `cycle_comparison`. A skill diz isso na `note` da avaliação; mudar a medida é decisão de desenho, fora do M3.
