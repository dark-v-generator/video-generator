# Implementation Plan: Ciclo de ajuste dos prompts

**Branch**: `006-prompt-tuning-cycle` (a criar a partir de `main`) | **Date**: 2026-09-29 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-prompt-tuning-cycle/spec.md`

## Summary

Uma rotina manual, conduzida por uma skill do projeto (`/prompt-tuning`), que a
cada pedido lê o histórico de desempenho, grava um **relatório de
acompanhamento** no repositório, publica uma **visão de leitura** descartável e
termina com uma recomendação: manter o ciclo aberto ou fechá-lo. Fechar o ciclo
é a única hora em que os prompts editoriais mudam; os experimentos podem mudar
em qualquer relatório.

São três peças:

1. **Registros em `tuning/`** (YAML, versionados ao lado dos prompts): crenças,
   experimentos, ciclos e relatórios, com um verificador e um resumo gerado.
2. **Pacote de dados** (`just tuning-data`): toda a aritmética do relatório
   (desempenho relativo aos vizinhos, vídeos assentados, progresso de cada
   experimento, fatia de exploração atingida, comparação entre ciclos) feita
   por código testado. A skill interpreta; não calcula.
3. **Exploração na rodada diária**: uma segunda nota por história, dada por um
   prompt próprio (`evaluate_exploration.jinja2`) que recebe os experimentos
   abertos como dados; a rodada reserva a fatia de exploração, entrega cada
   vaga ao experimento de maior prioridade com história adequada e grava no
   histórico o objetivo de cada vídeo.

Sem experimento aberto nada muda na rodada: nenhuma chamada a mais ao modelo,
mesma seleção, golden intocado.

## Technical Context

**Language/Version**: Python 3.12 (venv atual), `requires-python >= 3.11`.

**Primary Dependencies**: as atuais (pydantic, dependency-injector, jinja2,
litellm, PyYAML via `BaseYAMLModel`). **Nenhuma dependência nova.** A skill é um
`SKILL.md` em `.claude/skills/prompt-tuning/`; a visão de leitura usa a
ferramenta de Artifact da sessão.

**Storage**: dois lugares, com papéis separados (FR-041b).
- `tuning/` na raiz do repositório: arquivos YAML e um CSV, lidos e escritos
  pela skill e validados por `just tuning-check`. `tuning/exploration.yaml` é o
  único que a rodada diária lê. Vai para o servidor pelo `just deploy` (rsync),
  como os prompts.
- `.storage/history.sqlite`: ganha 4 colunas em `video_records` e 2 em
  `run_summaries`, pelo mesmo padrão idempotente de `_add_audience_columns`.

**Testing**: pytest sem rede e sem modelo. Novos: `FakeExplorationSource`,
`evaluate_exploration` no `FakeLLMProxy`, testes puros de alocação de vagas e de
desempenho relativo, esquema migrado sobre um SQLite criado antes da feature,
validação de `tuning/` sobre fixtures válidos e inválidos. Golden inalterado.

**Target Platform**: Linux (servidor: rodada diária lê `tuning/exploration.yaml`)
e macOS (laptop: skill, pacote de dados sobre o SQLite puxado por
`just sync-history`, edição dos prompts, `just deploy`).

**Project Type**: projeto único, Clean Architecture em módulos.

**Performance Goals**: SC-001: relatório lido e decidido em menos de 10 minutos
do operador; `just tuning-data` sobre o histórico inteiro em menos de 10 s
(~1 000 registros/ano). Custo da segunda nota: uma chamada a mais por finalista
(até 55 por dia: 11 subreddits × 5), no mesmo modelo barato da avaliação
(`deepseek-v4-flash`), e só enquanto houver experimento aberto.

**Constraints**:
- Prompts editoriais só mudam no fechamento de um ciclo (FR-021); os
  experimentos entram no prompt de exploração como variáveis, de modo que
  mudar um experimento não muda o fingerprint de nenhum template.
- `src/flows/daily_run.py` tem teto de 320 linhas e está em 315
  (`tests/flows/test_daily_run_shape.py`): a lógica de vagas fica fora do fluxo.
- Golden (`tests/flows/test_daily_run_golden.py`) inalterado.
- Mudança em `tuning/` ou nos prompts só vale no servidor depois de
  `just deploy`; a skill registra a data do deploy, não a da edição.
- Vídeo com menos de 7 dias não entra em achado nem veredito (FR-013).

**Scale/Scope**: 1 operador, 3 vídeos/dia, ~84 vídeos por janela de 30 dias,
fatia de exploração padrão 25% (≈ 5 vídeos por semana). 5 PRs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação | Resultado |
|-----------|-----------|-----------|
| I. Fail Fast e Simplicidade | `tuning/exploration.yaml` inválido derruba a rodada na carga, com o campo nomeado; arquivo ausente significa "sem experimentos", que é o estado de hoje. Falha ao dar a nota de exploração de uma história estoura a busca, como qualquer falha de descoberta, em vez de virar nota zero silenciosa. Vaga de exploração sem história adequada vai para a base e é contada: é o caso frequente, não um caso raro. Nenhuma fila com reposição de experimento, nenhum retry novo. `just tuning-data` sem coleta recente para e pede a coleta. | PASS |
| II. Arquitetura Limpa em Módulos | Entidades sem I/O em `src/entities/tuning.py`. Capacidade nova `src/capabilities/exploration/` com lógica pura (vagas, ordenação) e o contrato `ExplorationSource`. Capacidade nova `src/capabilities/tuning/` com a aritmética do relatório, pura, sobre `CrossedRow`. Leitura de arquivos em `src/storage/tuning_files.py`, atrás de contrato. A chamada ao modelo fica no proxy. O fluxo só conhece contratos. Scripts só traduzem argumentos. | PASS |
| III. Prompts Baseados em Racional | O prompt novo explica o que é um experimento e por que a nota mede se a história é um teste justo da pergunta; não lista casos. A skill é um prompt e segue a mesma regra: explica o que cada passo protege. As mudanças que a rotina propõe nos prompts editoriais são escritas como a razão pela qual a audiência responde (FR-019), e a skill recusa propor regra casuística. | PASS |
| Idioma | Plano, research, data-model, contracts e quickstart em português; código, nomes de arquivo, chaves YAML, comentários e commits em inglês. Conteúdo dos registros em `tuning/` (achados, crenças, perguntas) em português, por ser documentação voltada ao operador. `spec.md` em inglês, acompanhando o pedido (mesmo desvio das features 002 a 005). | PASS (desvio documentado) |

**Re-check pós-design (Phase 1)**: o desenho acrescenta uma segunda chamada ao
modelo por finalista e um diretório de registros fora de `src/`. Ambos
justificados em Complexity Tracking. O fluxo ganha uma dependência
(`exploration`) e três linhas; a regra de vagas é uma função pura testada sem
fluxo. PASS.

## Delivery Plan

5 milestones, 1 PR cada. Ordem: primeiro o que entrega as histórias P1
(registros, dados, skill), para o operador já ter relatório, recomendação e
ajuste de prompts; depois a exploração na rodada, que é P2 e a única parte que
toca a produção. O contrato do pacote de dados nasce completo no M2; os campos
de experimento ficam vazios até o M4. A rodada diária continua implantável ao
fim de cada PR.

### M1 — Registros em `tuning/`, verificador e resumo (US6, base de US1–US3) — PR 1

- `src/entities/tuning.py`: `Belief`, `Experiment`, `ExplorationPlan`, `Cycle`,
  `PromptChange`, `Report`, `Finding` (pydantic, sem I/O;
  [data-model.md](./data-model.md)).
- `src/storage/tuning_contract.py` + `src/storage/tuning_files.py`:
  `TuningRecords` (Protocol) e `FileTuningRecords(root)`; leitura de tudo,
  escrita só de `README.md` ([contracts/tuning-records.md](./contracts/tuning-records.md)).
- `src/core/paths.py`: `tuning_dir()` (`TUNING_DIR`, padrão `tuning/`).
- `src/entities/history.py` + `src/core/recipe.py`: `ProductionRecipe` ganha
  `hashtags_prompt_version` (FR-023 cobre o prompt de hashtags, que hoje não
  tem versão no registro).
- `scripts/tuning_check.py` (`just tuning-check`): valida formato e invariantes,
  inclusive que os fingerprints dos prompts em disco são os do ciclo aberto
  (FR-022).
- `scripts/tuning_summary.py` (`just tuning-summary`): gera `tuning/README.md`.
- Semente em `tuning/`: `cycles/001.yaml` (aberto, prompts atuais como linha de
  base), `beliefs.yaml` com os achados do relatório de setembro como **pistas**
  (84 vídeos, um mês), `exploration.yaml` sem experimentos, `story_labels.csv`
  só com o cabeçalho.
- Testes: `tests/storage/test_tuning_files.py`, `tests/scripts/test_tuning_check.py`
  (cada invariante com um fixture que a quebra), `test_tuning_summary.py`.

**Gate**: `uv run pytest -q` verde; `just tuning-check` passa sobre a semente;
editar uma linha de `src/prompts/story.jinja2` faz `just tuning-check` falhar
nomeando o prompt e as duas versões.

### M2 — Pacote de dados do relatório (US1, US5) — PR 2

- `src/capabilities/tuning/`: `relative.py` (desempenho relativo aos 10 vizinhos
  no tempo, vídeo assentado), `periods.py` (movimento semanal do canal, uploads
  perdidos), `cycles.py` (vídeos de base de um ciclo contra os do anterior),
  `progress.py` (por experimento: contagem, assentados, relativo mediano;
  fatia pretendida e atingida). Tudo puro, sobre `CrossedRow`.
- `scripts/tuning_data.py` (`just tuning-data`): `[--since DATA] [--days N]
  [--json ARQUIVO]`; recusa quando há menos vídeos assentados que o mínimo ou
  quando a última coleta é mais velha que o limite
  ([contracts/tuning-data.md](./contracts/tuning-data.md)).
- Testes: vizinhança nas bordas do período, empate de horário, vídeo sem
  snapshot, período curto, comparação entre ciclos com e sem mudança de modelo
  junto (a saída diz que o efeito não é atribuível).

**Gate**: `just sync-history && just tuning-data --since 2026-08-29 --until
2026-09-28` termina em menos de 10 s sobre o histórico real, considera os 84
vídeos do relatório de setembro, e o relativo de três vídeos escolhidos à mão
confere com a conta feita na planilha a partir de `just report --csv`.

### M3 — Skill `/prompt-tuning` e visão de leitura (US1, US2, US3, US5) — PR 3

- `.claude/skills/prompt-tuning/SKILL.md` e `references/` (formatos dos
  registros, roteiro da visão de leitura, critérios da recomendação):
  [contracts/skill.md](./contracts/skill.md).
- O que a skill faz, em ordem: `just tuning-check` → `just tuning-data` →
  rotula as histórias novas em `story_labels.csv` → escreve
  `tuning/reports/AAAA-MM-DD.yaml` → publica a visão de leitura → recomenda
  manter ou fechar → registra a decisão. Se o operador fecha: vereditos,
  atualização de crenças, proposta de mudança nos prompts (redação atual,
  proposta, achado), aplicação do que foi aprovado, `cycles/NNN.yaml` fechado e
  o seguinte aberto, `just tuning-summary`, lembrete de `just deploy`.
- Ajuste de experimentos em qualquer relatório: escreve `exploration.yaml`
  (FR-003a); as vagas só passam a existir no M5, e a skill diz isso enquanto o
  M5 não estiver implantado.
- `docs/tuning.md`: a rotina para o operador; `README.md` aponta para ele.

**Gate**: primeiro relatório real pelo [quickstart §3](./quickstart.md): registro
gravado, visão publicada, recomendação com motivos, `git status` sem mudança em
`src/prompts/`. Depois, um fechamento de ciclo de ensaio em um branch
descartável: `cycles/001.yaml` fechado, `002.yaml` aberto, `just tuning-check`
verde.

### M4 — Nota de exploração e objetivo no histórico (US4) — PR 4

- `src/prompts/evaluate_exploration.jinja2`: recebe a história e os experimentos
  abertos (`id`, `question`, `looks_like`); devolve o experimento que a história
  melhor serve, a nota de 0 a 100 e a justificativa.
- `src/proxies/interfaces.py`, `llm_prompt_proxy.py`, `llm_dspy_proxy.py`,
  `mock_llm_proxy.py`: `evaluate_exploration(title, content, experiments,
  target_language) -> dict`.
- `src/capabilities/discovery/`: `find_best_stories(..., experiments=())`; com
  experimentos, dá a segunda nota a todo finalista avaliado e devolve, além das
  histórias de base de hoje, as que atingem `min_fit`. `EvaluatedStory` ganha
  `exploration: ExplorationFit | None` e `goal: str = "base"`.
- `src/entities/history.py`, `src/storage/sqlite_history.py`,
  `tests/fakes/memory_history.py`: `VideoRecord.goal`, `.exploration_experiment`,
  `.exploration_fit`, `.cycle`; `ProductionRecipe.exploration_prompt_version`;
  colunas novas na visão cruzada; `goal_counts(since)`.
- `src/flows/run_record.py`: grava os quatro campos. Neste milestone todo vídeo
  sai com `goal="base"`.
- `just tuning-data` passa a preencher a seção de experimentos.

**Gate**: `uv run pytest -q` verde com golden intocado; com um experimento
aberto em um `TUNING_DIR` temporário, `just daily-generate 1` grava
`exploration_fit` e `exploration_experiment` no registro e `goal='base'`; um
`history.sqlite` de antes do PR abre e ganha as colunas sem perder linhas.

### M5 — Vagas de exploração na rodada diária (US4, US5) — PR 5

- `src/capabilities/exploration/`: `contract.py` (`ExplorationSource`),
  `allocation.py` (`slots_due`, `arrange`: puras;
  [contracts/exploration.md](./contracts/exploration.md)).
- `src/flows/daily_run.py`: recebe `exploration: ExplorationSource`; em `_find`
  passa os experimentos abertos à descoberta e ordena as candidatas com
  `arrange`. Nenhuma mensagem de progresso muda quando não há experimento.
- `src/flows/run_record.py`: `RunSummary.exploration_slots` e
  `.exploration_filled`.
- `src/core/container.py`: provider `exploration_source`.
- `docs/architecture.md`, `docs/configuration.md` (`TUNING_DIR`), `docs/tuning.md`.
- Testes: alocação (fatia fracionária ao longo de vários dias, teto diário, dia
  sem história adequada, prioridade entre experimentos, história que serve a
  dois); fluxo com `FakeExplorationSource`.

**Gate**: simulação de 12 dias com fatia 0,25 e alvo 3 produz 9 vídeos de
exploração em 36 (±1); um dia sem história adequada produz 3 de base e
`exploration_filled=0`; golden intocado; no servidor, a primeira rodada depois
do deploy com um experimento aberto mostra `goal` preenchido em `just report`.

## Project Structure

### Documentation (this feature)

```text
specs/006-prompt-tuning-cycle/
├── plan.md              # este arquivo
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1: validação por milestone
├── contracts/
│   ├── tuning-records.md   # arquivos de tuning/, TuningRecords, invariantes do check
│   ├── tuning-data.md      # just tuning-data: argumentos e formato do pacote
│   ├── exploration.md      # prompt, proxy, descoberta, vagas, histórico, DailyRun
│   └── skill.md            # /prompt-tuning: passos, saídas, visão de leitura
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
tuning/                                # NOVO (M1): registros, versionados
├── exploration.yaml                   # fatia, prioridade e experimentos (lido pela rodada)
├── beliefs.yaml
├── story_labels.csv
├── cycles/001.yaml
├── reports/AAAA-MM-DD.yaml
└── README.md                          # gerado por just tuning-summary
.claude/skills/prompt-tuning/          # NOVO (M3)
├── SKILL.md
└── references/{records.md, reading-view.md, recommendation.md}
src/
├── entities/
│   ├── tuning.py                      # NOVO (M1)
│   ├── history.py                     # M1: hashtags_prompt_version; M4: goal, exploration_*, cycle
│   └── story_candidate.py             # M4: ExplorationFit, EvaluatedStory.exploration/.goal
├── prompts/evaluate_exploration.jinja2   # NOVO (M4)
├── proxies/
│   ├── interfaces.py, llm_prompt_proxy.py, llm_dspy_proxy.py, mock_llm_proxy.py   # M4
├── capabilities/
│   ├── discovery/contract.py, reddit_discovery.py   # M4: experiments=
│   ├── tuning/                        # NOVO (M2): relative, periods, cycles, progress
│   └── exploration/                   # NOVO (M5): contract, allocation
├── storage/
│   ├── tuning_contract.py, tuning_files.py   # NOVO (M1)
│   ├── history_contract.py            # M4: goal_counts
│   └── sqlite_history.py              # M4: colunas e visão cruzada
├── flows/
│   ├── daily_run.py                   # M5: exploration, arrange
│   └── run_record.py                  # M4: objetivo no registro; M5: vagas no resumo
└── core/
    ├── paths.py                       # M1: tuning_dir
    ├── recipe.py                      # M1, M4: versões dos prompts novos
    └── container.py                   # M5: exploration_source
scripts/
├── tuning_check.py, tuning_summary.py # NOVO (M1)
└── tuning_data.py                     # NOVO (M2)
tests/
├── fakes/exploration.py               # NOVO (M5); fakes/proxies.py, memory_history.py (M4)
├── fixtures/tuning/{valid,broken-*}/  # NOVO (M1)
├── capabilities/test_tuning_relative.py, test_tuning_progress.py, test_exploration_allocation.py
├── storage/test_tuning_files.py, test_sqlite_history.py (M4)
├── flows/test_daily_run_exploration.py
└── scripts/test_tuning_check.py, test_tuning_summary.py, test_tuning_data.py
Justfile                               # M1: tuning-check, tuning-summary; M2: tuning-data
docs/tuning.md                         # NOVO (M3); architecture.md, configuration.md (M5)
```

**Structure Decision**: projeto único, mesma disposição das features 004 e 005.
Os registros ficam em `tuning/`, fora de `src/`, porque são dados que o
operador lê e a skill escreve; o código só os lê. A rodada depende de um único
arquivo desse diretório, por trás de `ExplorationSource`.

## Verificação pós-implementação

- Golden intocado em todos os PRs; `uv run pytest -q` verde sem rede e sem
  modelo.
- `grep -rn "tuning/" src/` só em `src/core/paths.py`; `grep -rn "yaml" src/flows/`
  vazio (o fluxo não sabe que o plano vem de arquivo).
- `wc -l src/flows/daily_run.py` ≤ 320.
- Sequência real: `/prompt-tuning` no laptop → relatório → abrir um experimento
  → `just deploy` → rodadas diárias → `just prod-collect-performance` →
  `/prompt-tuning` de novo mostra o progresso do experimento → ao atingir o
  alvo, veredito e recomendação de fechar.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Segunda chamada ao modelo por finalista (prompt próprio para a nota de exploração) | Os experimentos mudam em qualquer relatório e os prompts editoriais só no fechamento do ciclo; a nota de base não pode ser influenciada pelo texto dos experimentos (FR-030) | Pedir as duas notas na mesma chamada colocaria os experimentos dentro do prompt de avaliação: cada mudança de experimento mudaria a nota de base e o fingerprint, e os vídeos de base de um ciclo deixariam de ser comparáveis |
| Diretório `tuning/` com registros em arquivos, ao lado do SQLite | O registro precisa viajar com o prompt que ele explica, ser lido sem ferramenta e aparecer no `git diff` de cada decisão (FR-041, FR-044, FR-045) | Guardar no SQLite deixaria as decisões fora do controle de versão e no servidor, longe dos prompts; o banco é puxado do servidor por rsync e seria sobrescrito |
| Rótulos de tipo de história gravados (`story_labels.csv`) | Dois relatórios seguidos precisam classificar o mesmo vídeo do mesmo jeito, senão um achado muda sem que nenhum dado tenha mudado (FR-015) | Classificar de novo a cada relatório custa mais tempo do modelo e torna os achados irreprodutíveis |
| Script `tuning_data.py` separado de `performance_report.py` | O relatório de ajuste precisa de números derivados (relativo aos vizinhos, assentado, por ciclo, por experimento) que a visão cruzada não tem e que não podem ficar a cargo do modelo | Deixar a skill calcular a partir do CSV tornaria os números dependentes de quem os calcula; colocar na visão cruzada misturaria leitura de registro com análise |
