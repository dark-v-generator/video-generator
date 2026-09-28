# Quickstart: validação por milestone

**Feature**: 005-video-performance-history

Cada seção prova o gate de um milestone do [plan.md](./plan.md). §1, §2 e §5
rodam no laptop com `config.dev.yaml` (LLM mock, edge-tts, whisper local); §3 e
§4 precisam do servidor, onde vivem a sessão do TikTok e o CSV real. Nenhum passo
chama modelo pago.

## Pré-requisitos

```bash
uv sync
cp config.dev.yaml config.yaml         # se ainda não houver um config.yaml local
uv run pytest -q                       # linha de base verde antes de começar
export HISTORY_DB_PATH=/tmp/history-quickstart.sqlite   # não misturar com .storage/
```

## §1 — M1: registro por vídeo e por rodada

```bash
uv run pytest tests/flows/test_daily_run_golden.py tests/flows/test_daily_run_history.py tests/storage -q
git diff --stat tests/fixtures/daily_run_golden.json      # esperado: vazio (SC-006)
rm -f "$HISTORY_DB_PATH"; just daily-generate 1
sqlite3 "$HISTORY_DB_PATH" "select count(*) from video_records; select source,count(*) from reddit_snapshots group by 1; select count(*) from publish_attempts; select mode,produced,scheduled,skipped_json from run_summaries;"
```

Esperado: `1`; `discovery|1`; `0`; `generate|1|0|{...}` com `not_needed` =
candidatas encontradas − 1 e os outros motivos em zero. Depois `just daily-publish-only output/daily` com o publisher falso do dev
(ou o real no servidor) acrescenta 1 linha em `publish_attempts` no **mesmo**
registro (`select record_id,status from publish_attempts`).

## §2 — M2: receita e importação

```bash
uv run pytest tests/prompts tests/scripts/test_import_history.py -q
just daily-generate 1
sqlite3 "$HISTORY_DB_PATH" "select story_prompt_version, writer_model, rendering_strategy, speech_rate, voice_id, duration_seconds from video_records order by id desc limit 1;"
sed -i '' '1s/^/{# quickstart #}\n/' src/prompts/story.jinja2 && just daily-generate 1
sqlite3 "$HISTORY_DB_PATH" "select id, story_prompt_version from video_records order by id desc limit 2;"
git checkout src/prompts/story.jinja2
just import-history --csv .storage/tiktok_publish_log.csv --manifests output/daily
just import-history --csv .storage/tiktok_publish_log.csv --manifests output/daily   # segunda vez
```

Esperado: os dois últimos registros têm `story_prompt_version` diferentes e
`writer_model`/`rendering_strategy` iguais; `duration_seconds` > 0; a primeira
importação cria uma `publish_attempts` por linha do CSV, a segunda imprime
"0 registros criados, 0 tentativas, N já existiam". No servidor:
`just prod-import-history`.

## §3 — M3: leitor do Studio (servidor)

```bash
just deploy
just prod-tiktok-studio-probe          # grava .storage/tiktok_studio_probe/<ts>/ no servidor
just sync-tiktok-studio-probe && ls .storage/tiktok_studio_probe/*/ | head
uv run pytest tests/proxies/test_tiktok_studio_proxy.py -q
```

Esperado: o dump contém ao menos uma resposta com a lista de vídeos (ids,
legendas, contagens) e uma de analytics; o fixture
`tests/fixtures/tiktok_studio_probe.json` está redigido (sem cookies, sem ids
de conta) e o parser passa sobre ele. Com a sessão apagada
(`just prod-tiktok-reset`, **só em teste consciente**), a sondagem termina com
`TikTokSessionExpiredError`; refazer o bootstrap depois.

## §4 — M4: coleta (servidor) e casamento (laptop)

```bash
uv run pytest tests/capabilities/test_performance_matching.py tests/flows/test_collect_performance.py tests/flows/test_adapters.py -q
just prod-collect-performance 30       # roda no servidor, puxa o sqlite no fim
sqlite3 .storage/history.sqlite "select matched,unmatched,ambiguous,reddit_refreshed from collections order by id desc limit 1; select count(*) from performance_snapshots; select source,count(*) from reddit_snapshots group by 1;"
just prod-collect-performance 30 && sqlite3 .storage/history.sqlite "select count(*) from performance_snapshots;"
```

Esperado: a primeira coleta reporta "K casados, U sem par, A ambíguos" com K ≥
95 % dos vídeos publicados pelo sistema no período (SC-002); `performance_snapshots`
tem K linhas e `reddit_snapshots` ganhou K com `source=collection`; a segunda
coleta dobra as linhas de snapshots sem alterar as antigas. Um não casado é
resolvido com `just prod-collect-performance "--assign <tiktok_id> <record_id>"`
e some do relatório da coleta seguinte. Pelo bot: `/collect 30` responde com
as mesmas linhas de progresso e recusa se uma rodada estiver em andamento.

## §5 — M5: visão cruzada (laptop, sobre o sqlite sincronizado)

```bash
just sync-history
time just report --sort grade_overall:desc                     # SC-004: < 10 s
just report --sort latest_views                                # nota alta, poucas views, no topo
just report --sort latest_views:desc --filter grade_verdict=Mediana
just report --filter story_prompt_version=<hash> --csv /tmp/cross.csv && head -3 /tmp/cross.csv
uv run pytest tests/scripts/test_performance_report.py tests/storage -q
```

Esperado: a tabela mostra, por vídeo, nota e sub-notas, upvotes na descoberta e
agora, e as métricas do TikTok (vazias para vídeos ainda sem coleta, não
omitidos); as duas ordenações respondem SC-003 sem abrir arquivo ou o TikTok; o
CSV tem as mesmas linhas com todas as colunas; `--columns` lista as colunas
válidas e uma coluna errada estoura nomeando-as.

## Verificação final

```bash
uv run pytest -q
git diff --stat main -- tests/fixtures/daily_run_golden.json    # vazio
grep -rn "sqlite3" src | grep -v src/storage/sqlite_history.py  # vazio
grep -rn "patchright" src | grep -v src/proxies/                 # vazio
```
