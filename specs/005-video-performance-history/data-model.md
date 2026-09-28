# Data Model: Histórico de desempenho dos vídeos

**Feature**: 005-video-performance-history | **Date**: 2026-09-28

Entidades sem I/O em `src/entities/history.py` (dataclasses `frozen=True`,
exceto onde o fluxo completa campos). Timestamps são `datetime` com fuso UTC;
no SQLite viram texto ISO 8601. Só resultados: nenhum campo guarda raciocínio,
prompt renderizado, rascunho ou trace (FR-007).

## VideoRecord (M1)

Um por vídeo renderizado. Partes de uma história são registros irmãos que
compartilham os campos de história.

| Campo | Tipo | Origem | Regra |
|-------|------|--------|-------|
| `id` | `int` | SQLite (autoincrement) | chave |
| `created_at` | `datetime` | `DailyRun.now()` no `_produce` | |
| `run_id` | `int \| None` | `RunSummary` da rodada | referência solta (FR-007b); `None` em importados |
| `video_path` | `str` | manifest | mesma string do manifest e do CSV; **não é único**: a rodada diária reescreve `output/daily/story_NN.mp4` todo dia, e a busca por caminho devolve o registro mais novo |
| `title` | `str` | `GeneratedVideo.title` (com sufixo da parte) | é a legenda publicada sem hashtags |
| `summary` | `str` | `GeneratedVideo.summary` | |
| `post_url` | `str` | `story.origin.url` | identifica a história |
| `community`, `author` | `str` | `RedditPost` | |
| `post_created_utc` | `datetime \| None` | `RedditPost.created_utc` | |
| `part_index`, `part_count` | `int` | `Story` | 1/1 para uma parte |
| `language` | `str` | `DailyRunConfig.language` | |
| `duration_seconds` | `float \| None` | `RenderedPart.duration_seconds` (M2) | `None` em importados |
| `grade` | `ModelGrade \| None` | `EvaluatedStory.evaluation` | `None` em importados |
| `deterministic_score` | `float \| None` | `EvaluatedStory.deterministic_score` | |
| `recipe` | `ProductionRecipe \| None` | container + voz por história (M2) | `None` em importados |
| `hashtags` | `list[str]` | primeira `PublishAttempt` | vazio até publicar |
| `tiktok_video_id` | `str \| None` | coleta (casamento) ou `--assign` | único quando presente |
| `imported` | `bool` | `import_history.py` | `True` = veio do CSV/manifests |

Relações: 1 → N `RedditSnapshot`, 1 → N `PublishAttempt`, 1 → N
`PerformanceSnapshot`.

## RedditSnapshot (M1 descoberta, M4 coleta)

| Campo | Tipo | Regra |
|-------|------|-------|
| `record_id` | `int` | FK |
| `taken_at` | `datetime` | |
| `source` | `"discovery" \| "collection"` | |
| `score`, `num_comments` | `int \| None` | `None` quando `available=False` |
| `upvote_ratio` | `float \| None` | |
| `available` | `bool` | `False` = post removido/indisponível na coleta |

## ModelGrade (M1)

Copiado de `EvaluatedStory.evaluation` (chaves do prompt `evaluate_story`).

| Campo | Tipo | Origem |
|-------|------|--------|
| `overall` | `float` | `nota_geral` (0–100) |
| `verdict` | `str` | `veredito` (`Excelente`, `Boa`, `Mediana`, `Fraca`, `Erro`) |
| `retention`, `quality`, `virality`, `tiktok_fit`, `hook` | `float \| None` | `notas.<k>.nota`; `None` quando a avaliação falhou (`notas = {}`) |
| `summary` | `str` | `resumo` (já é o que vai ao manifest, truncado a 400) |

As justificativas por sub-nota **não** são gravadas (processo, FR-007).

## ProductionRecipe (M2)

| Campo | Tipo | Origem |
|-------|------|--------|
| `story_prompt_version` | `str` | `prompts.fingerprint("story.jinja2")` |
| `grading_prompt_version` | `str` | `prompts.fingerprint("evaluate_story.jinja2")` |
| `writer_model` | `str` | `provider/model` de `history_adaptation_llm_config` ou `llm_config` (`mock` → `"mock"`) |
| `grader_model` | `str` | idem de `llm_config` |
| `rendering_strategy` | `str` | `video_config.rendering_strategy` |
| `speech_provider` | `str` | `speech_config.type` |
| `speech_rate` | `float \| None` | `default_rate` (edge-tts) |
| `narrator_gender` | `"male" \| "female"` | `story.resolved_gender` |
| `voice_id` | `str` | `ISpeechProxy.voice_id(resolved_gender, language)` |

Os campos fixos por processo são montados pelo container; `narrator_gender` e
`voice_id` são completados pelo fluxo por história (`dataclasses.replace`).

## PublishAttempt (M1)

Uma por chamada ao publisher, espelho da linha do CSV.

| Campo | Tipo | Regra |
|-------|------|-------|
| `record_id` | `int` | FK |
| `attempted_at` | `datetime` | = `created_at` da linha do CSV |
| `status` | `"scheduled" \| "failed"` | |
| `scheduled_at` | `datetime \| None` | slot |
| `hashtags` | `list[str]` | |
| `publish_result` | `str` | URL devolvida pelo publisher, se houver |
| `error` | `str` | vazio em sucesso |

## PerformanceSnapshot (M4)

| Campo | Tipo | Regra |
|-------|------|-------|
| `record_id` | `int` | FK |
| `collection_id` | `int` | FK para `Collection` |
| `taken_at` | `datetime` | |
| `tiktok_video_id` | `str` | |
| `views`, `likes`, `comments`, `shares`, `saves` | `int \| None` | `None` quando o Studio não expõe |
| `avg_watch_seconds` | `float \| None` | analytics por vídeo |
| `full_watch_ratio` | `float \| None` | 0–1, "assistiu até o fim" |
| `tiktok_created_at` | `datetime \| None` | `createTime` do post |

## TikTokVideoStats (M3)

O que o proxy do Studio devolve por vídeo, antes do casamento: `video_id`,
`description`, `created_at`, e os mesmos campos numéricos de
`PerformanceSnapshot` (sem `record_id`/`collection_id`). `PerformanceMetrics`
é o subconjunto numérico devolvido pela analytics por vídeo.

## Collection e CollectionReport (M4)

`Collection` (tabela `collections`): `id`, `started_at`, `finished_at`,
`lookback_days`, `matched`, `unmatched`, `ambiguous`, `reddit_refreshed`.

`CollectionReport` (entidade devolvida ao adaptador): as contagens acima mais
`unmatched_videos: list[TikTokVideoStats]` e
`ambiguous: list[tuple[TikTokVideoStats, list[int]]]` (ids dos registros
candidatos). Não é persistida além das contagens: a lista de não casados se
recalcula na próxima coleta.

## RunSummary (M1)

| Campo | Tipo | Regra |
|-------|------|-------|
| `id` | `int` | chave |
| `started_at` | `datetime` | gravado por `start_run` |
| `finished_at` | `datetime \| None` | gravado por `finish_run`; `None` = rodada não terminou |
| `mode` | `"run" \| "generate" \| "publish"` | |
| `requested`, `target` | `int` | `count` pedido e `min(count, candidatas)` |
| `candidates_found` | `int` | tamanho da lista da descoberta (0 se a busca falhou) |
| `produced`, `scheduled` | `int` | vídeos |
| `skipped` | `dict[SkipReason, int]` | `content_filter`, `script`, `render`, `publish`, `not_needed` |
| `stopped_reason` | `str` | vazio, `discovery_failed`, `no_candidates` |

Independente de `VideoRecord` (FR-007b): nenhuma FK de `run_summaries` para
`video_records`; `VideoRecord.run_id` é referência solta sem restrição.

## CrossedRow (M5)

Projeção, não tabela: campos de `VideoRecord` + `ModelGrade` + `ProductionRecipe`
achatados, `discovery_*` (score, comentários, ratio e data do snapshot `discovery`),
`latest_reddit_*` (último snapshot `collection`: vídeo nunca coletado não tem
"agora"; mais `latest_reddit_available`), `latest_*` (último `PerformanceSnapshot`,
`None` quando não há), `last_attempt_status`, `last_scheduled_at` (da última
tentativa). `CrossedRow.columns()` achata a linha em `CROSSED_COLUMNS` (53 nomes,
em `src/entities/history.py`, reexportada por `src/storage`), que são os nomes
aceitos por `--sort`/`--filter` e as colunas do CSV. Vazios ordenam no fim nos dois
sentidos, empates por id; filtro compara número como número e o resto como texto.

## Esquema SQLite (M1, M4)

```sql
CREATE TABLE IF NOT EXISTS run_summaries (
  id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
  mode TEXT NOT NULL, requested INTEGER, target INTEGER, candidates_found INTEGER,
  produced INTEGER, scheduled INTEGER, skipped_json TEXT NOT NULL, stopped_reason TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS video_records (
  id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, run_id INTEGER,
  video_path TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL DEFAULT '',
  post_url TEXT NOT NULL, community TEXT, author TEXT, post_created_utc TEXT,
  part_index INTEGER NOT NULL DEFAULT 1, part_count INTEGER NOT NULL DEFAULT 1,
  language TEXT, duration_seconds REAL,
  grade_overall REAL, grade_verdict TEXT, grade_retention REAL, grade_quality REAL,
  grade_virality REAL, grade_tiktok_fit REAL, grade_hook REAL, deterministic_score REAL,
  story_prompt_version TEXT, grading_prompt_version TEXT, writer_model TEXT, grader_model TEXT,
  rendering_strategy TEXT, speech_provider TEXT, speech_rate REAL, narrator_gender TEXT, voice_id TEXT,
  hashtags TEXT NOT NULL DEFAULT '', tiktok_video_id TEXT UNIQUE, imported INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS video_records_by_path ON video_records (video_path);
CREATE TABLE IF NOT EXISTS reddit_snapshots (
  id INTEGER PRIMARY KEY, record_id INTEGER NOT NULL REFERENCES video_records(id),
  taken_at TEXT NOT NULL, source TEXT NOT NULL, score INTEGER, num_comments INTEGER,
  upvote_ratio REAL, available INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS publish_attempts (
  id INTEGER PRIMARY KEY, record_id INTEGER NOT NULL REFERENCES video_records(id),
  attempted_at TEXT NOT NULL, status TEXT NOT NULL, scheduled_at TEXT, hashtags TEXT NOT NULL DEFAULT '',
  publish_result TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '',
  UNIQUE(record_id, attempted_at));
CREATE TABLE IF NOT EXISTS collections (
  id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT NOT NULL, lookback_days INTEGER,
  matched INTEGER, unmatched INTEGER, ambiguous INTEGER, reddit_refreshed INTEGER);
CREATE TABLE IF NOT EXISTS performance_snapshots (
  id INTEGER PRIMARY KEY, record_id INTEGER NOT NULL REFERENCES video_records(id),
  collection_id INTEGER NOT NULL REFERENCES collections(id), taken_at TEXT NOT NULL,
  tiktok_video_id TEXT NOT NULL, views INTEGER, likes INTEGER, comments INTEGER, shares INTEGER, saves INTEGER,
  avg_watch_seconds REAL, full_watch_ratio REAL, tiktok_created_at TEXT);
-- M5: "último snapshot/tentativa por registro" na visão cruzada
CREATE INDEX IF NOT EXISTS reddit_snapshots_by_record ON reddit_snapshots (record_id);
CREATE INDEX IF NOT EXISTS publish_attempts_by_record ON publish_attempts (record_id);
CREATE INDEX IF NOT EXISTS performance_snapshots_by_record ON performance_snapshots (record_id);
```

A receita é achatada em `video_records` (uma linha por vídeo, sem tabela de
receitas): filtrar por `story_prompt_version` é um `WHERE` direto e a visão
cruzada não precisa de `JOIN` extra. Hashtags como texto `#a #b`, igual ao CSV.

## Transições

- `VideoRecord`: criado sem tentativas → ganha `PublishAttempt` `failed` e/ou
  `scheduled` (nunca substitui) → ganha `tiktok_video_id` na primeira coleta
  casada ou por `--assign` → ganha `PerformanceSnapshot` a cada coleta.
- `RunSummary`: linha aberta no início da rodada (`start_run`, contagens
  zero, `finished_at` nulo) e concluída no fim (`finish_run`), inclusive quando
  ela para cedo (`stopped_reason`). `finished_at` nulo depois do fato significa
  que a rodada estourou no meio.
- `Collection`: linha escrita na mesma transação dos snapshots; coleta que falha
  não deixa linha.
