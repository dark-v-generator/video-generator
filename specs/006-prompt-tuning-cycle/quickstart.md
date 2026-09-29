# Quickstart: validação por milestone

**Feature**: 006-prompt-tuning-cycle

Cada seção prova o gate de um milestone do [plan.md](./plan.md). §1, §2, §4 e a
primeira parte de §5 rodam no laptop sem modelo pago. §3 usa a sessão do
assistente. O fim de §5 precisa do servidor.

## Pré-requisitos

```bash
uv sync
uv run pytest -q                                   # linha de base verde
just sync-history                                  # histórico real em .storage/
export TUNING_DIR=/tmp/tuning-quickstart           # só nos passos que pedem
```

## §1 — M1: registros, verificador e resumo

```bash
uv run pytest tests/storage/test_tuning_files.py tests/scripts/test_tuning_check.py tests/scripts/test_tuning_summary.py -q
just tuning-check
just tuning-summary && git diff --stat tuning/README.md
```

Esperado: check verde sobre a semente; README com o ciclo 1 aberto, as crenças
de setembro listadas como pistas e nenhum experimento.

Mudança fora da rotina:

```bash
sed -i '' '1s/^/{# quickstart #}\n/' src/prompts/story.jinja2
just tuning-check; echo "saída: $?"
git checkout src/prompts/story.jinja2
```

Esperado: falha nomeando `story`, com a versão registrada e a do disco; saída 1.

## §2 — M2: pacote de dados

```bash
uv run pytest tests/capabilities/test_tuning_relative.py tests/capabilities/test_tuning_progress.py tests/scripts/test_tuning_data.py -q
time just tuning-data --since 2026-08-29 --until 2026-09-28 --json /tmp/pack.json
python -c "import json; p=json.load(open('/tmp/pack.json')); print(p['videos'], len(p['rows']))"
```

Esperado: menos de 10 s; 84 vídeos no período. Conferir à mão o `relative` de
três vídeos contra `just report --since 2026-08-29 --csv /tmp/cross.csv`.

Recusas:

```bash
just tuning-data --days 3; echo "saída: $?"          # poucos vídeos assentados
just tuning-data --max-age-days 0; echo "saída: $?"  # coleta velha
```

Esperado: saída 2 e uma linha dizendo o que fazer, nas duas.

## §3 — M3: skill

Primeiro relatório, em um branch descartável:

```bash
git switch -c tuning-rehearsal
```

Na sessão do assistente: `/prompt-tuning`.

Esperado, em ordem: rótulos novos em `tuning/story_labels.csv`; um arquivo em
`tuning/reports/`; link da visão de leitura; recomendação com motivos; pergunta
sobre a decisão.

```bash
just tuning-check
git status --short src/prompts/          # esperado: vazio
```

Fechamento de ensaio: `/prompt-tuning close`, aprovar uma mudança e rejeitar
outra.

```bash
just tuning-check
ls tuning/cycles/                        # 001.yaml fechado, 002.yaml aberto
git diff --stat src/prompts/             # só o prompt da mudança aprovada
git switch main && git branch -D tuning-rehearsal
```

Tempo do operador: relatório lido e decidido em menos de 10 minutos (SC-001);
fechamento em menos de 45 (SC-002).

## §4 — M4: nota de exploração e objetivo no histórico

```bash
uv run pytest tests/capabilities/test_discovery.py tests/storage/test_sqlite_history.py tests/flows/test_daily_run_golden.py -q
git diff --stat tests/fixtures/daily_run_golden.json      # esperado: vazio
```

Migração sobre um banco de antes do PR:

```bash
cp .storage/history.sqlite /tmp/history-before.sqlite
HISTORY_DB_PATH=/tmp/history-before.sqlite just report --columns | grep -E "goal|exploration|cycle"
sqlite3 /tmp/history-before.sqlite "select count(*), count(goal) from video_records;"
```

Esperado: as colunas novas listadas; mesma contagem de linhas de antes e
`count(goal)` igual a 0.

Com um experimento aberto (`config.dev.yaml`, modelo mock):

```bash
mkdir -p $TUNING_DIR && cp -r tests/fixtures/tuning/valid/* $TUNING_DIR/
export HISTORY_DB_PATH=/tmp/history-quickstart.sqlite; rm -f $HISTORY_DB_PATH
just daily-generate 1
sqlite3 $HISTORY_DB_PATH "select goal, exploration_experiment, exploration_fit, cycle, exploration_prompt_version from video_records;"
```

Esperado: `base`, o experimento e a nota que o mock devolveu, o ciclo do plano
e a versão do prompt de exploração.

## §5 — M5: vagas de exploração

```bash
uv run pytest tests/capabilities/test_exploration_allocation.py tests/flows/test_daily_run_exploration.py tests/flows/test_daily_run_golden.py tests/flows/test_daily_run_shape.py -q
git diff --stat tests/fixtures/daily_run_golden.json      # esperado: vazio
wc -l src/flows/daily_run.py                              # ≤ 320
```

O teste de alocação cobre a simulação de 12 dias (9 de exploração em 36, ±1) e
o dia sem história adequada (3 de base, `exploration_filled=0`).

No servidor, depois de abrir um experimento pela skill:

```bash
just deploy
# depois da rodada diária seguinte:
just sync-history
just report --since $(date +%F) --filter goal=E001
sqlite3 .storage/history.sqlite "select started_at, exploration_slots, exploration_filled from run_summaries order by id desc limit 3;"
```

Esperado: ao menos um vídeo com `goal=E001` nos primeiros dois dias (a conta
acumulada dá 1, 1, 0, 1), ou `exploration_filled=0` com a vaga contada quando
nenhuma história serviu.

## Verificação final

```bash
uv run pytest -q
grep -rn "tuning/" src/ | grep -v "src/core/paths.py"     # esperado: vazio
grep -rn "yaml" src/flows/                                 # esperado: vazio
```
