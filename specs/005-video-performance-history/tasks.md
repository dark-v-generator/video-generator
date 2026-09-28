# Tasks: Histórico de desempenho dos vídeos

**Input**: Design documents from `/specs/005-video-performance-history/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: incluídos. O spec exige o golden da rodada inalterado (SC-006), casamento
automático verificável (SC-002) e a visão cruzada respondendo sem abrir arquivos
(SC-003); cada gate depende de testes que rodam sem rede, modelo ou Chromium.

**Organization**: uma fase por milestone do plano. O milestone é a unidade de merge
(1 PR); as tarefas são commits dentro dele. A fundação (entidades, contrato e
SQLite) entra no PR 1 junto com a US1.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tarefa aberta)
- **[Story]**: user story do spec (US1..US4)
- Caminhos exatos em cada descrição

## Delivery Plan

| PR | Milestone | Stories | Gate |
|----|-----------|---------|------|
| 1 | M1 — Registro por vídeo e por rodada | US1 | golden intocado; `just daily-generate 1` deixa 1 `video_records`, 1 `reddit_snapshots` (`discovery`), 0 `publish_attempts`, 1 `run_summaries`; publish-only acrescenta a tentativa no mesmo registro |
| 2 | M2 — Receita de produção e importação do passado | US4, US1 (FR-017) | editar `story.jinja2` muda só `story_prompt_version`; `duration_seconds` > 0; `import-history` cria 1 tentativa por linha do CSV e roda duas vezes sem duplicar |
| 3 | M3 — Leitor do TikTok Studio | US2 | sondagem no servidor gera o dump; fixture redigido no PR; parser passa sobre ele; sessão expirada estoura |
| 4 | M4 — Coleta, casamento e atualização do Reddit | US2 | `prod-collect-performance` reporta K casados (≥ 95 %); snapshots de TikTok e Reddit gravados; segunda coleta acrescenta sem alterar; `--assign` resolve; `/collect` recusa com rodada em andamento |
| 5 | M5 — Visão cruzada, sincronização e docs | US3 | `just report` < 10 s; ordenações de SC-003; CSV com as mesmas linhas; docs atualizadas |

**Projeção**: 5 PRs.

---

## Phase 1: Setup

- [X] T001 Criar a branch `005-video-performance-history` a partir de `main`; levar para ela `specs/005-video-performance-history/`, `.specify/feature.json` e a mudança de `AGENTS.md`; registrar a linha de base `uv run pytest -q` (número de testes coletados e falhas) na seção Notes deste arquivo

---

## Phase 2: Fundação (dentro do PR 1)

**Purpose**: entidades do histórico, contrato `HistoryStore` e as duas implementações
(SQLite e memória). Bloqueia todas as stories.

- [X] T002 [P] Criar `src/entities/history.py` com as dataclasses de [data-model.md](./data-model.md): `RedditSnapshot`, `ModelGrade` (com `from_evaluation(evaluation: dict) -> ModelGrade`, sub-notas `None` quando `notas` está vazio), `ProductionRecipe` (com `ProductionRecipe.empty()`), `PublishAttempt`, `PerformanceMetrics`, `TikTokVideoStats`, `PerformanceSnapshot`, `VideoRecord`, `SkipReason` (Literal `content_filter | script | render | publish | not_needed`), `RunSummary`, `Collection`, `CollectionReport`, `CrossedRow`; sem I/O; docstring de módulo dizendo que só resultados entram aqui (FR-007)
- [X] T003 [P] Criar `src/storage/history_contract.py` com o Protocol `HistoryStore` (métodos M1 de [contracts/history-storage.md](./contracts/history-storage.md): `start_run`, `finish_run`, `add_video_record`, `find_record_by_video_path`, `add_publish_attempt`, `publish_attempts(record_id)`) e exportá-lo em `src/storage/__init__.py`
- [X] T004 Criar `src/storage/sqlite_history.py` com `SqliteHistoryStore(path)`: cria o diretório e o esquema de [data-model.md](./data-model.md) na construção, `PRAGMA journal_mode=WAL` e `foreign_keys=ON`, helpers `_to_iso`/`_from_iso` em UTC, uma transação por método, `UNIQUE(record_id, attempted_at)` estourando em tentativa repetida, `add_video_record(record, None)` gravando `imported=1` sem snapshot
- [X] T005 [P] Criar `tests/fakes/memory_history.py` com `InMemoryHistoryStore` (mesmo contrato sobre listas e dicionários, ids sequenciais, mesma exceção em tentativa repetida)
- [X] T006 Criar `tests/storage/test_sqlite_history.py` parametrizado sobre `SqliteHistoryStore` (arquivo em `tmp_path`) e `InMemoryHistoryStore`: esquema criado do zero, `start_run` devolve id e `finish_run` completa a linha, registro com snapshot de descoberta, tentativa `failed` e depois `scheduled` no mesmo registro (as duas preservadas), tentativa duplicada estoura, `find_record_by_video_path`, registro importado sem snapshot, datas voltam com fuso UTC
- [X] T007 Em `src/core/container.py` adicionar `_history_db_path()` (lê `HISTORY_DB_PATH`, padrão `.storage/history.sqlite`) e o provider `history_store = providers.Factory(SqliteHistoryStore, path=providers.Callable(_history_db_path))`; cobrir em `tests/test_container_config.py` que a variável de ambiente é lida a cada chamada

---

## Phase 3: Milestone 1 — Registro por vídeo e por rodada (US1) — PR 1

**Goal**: a rodada diária, nos três modos, deixa um `VideoRecord` por vídeo (sinais
do Reddit na descoberta, nota, fatos do vídeo), uma `PublishAttempt` por tentativa
e um `RunSummary` por rodada, sem mudar mensagens, manifests, CSV nem golden.

**Independent test criteria**:
- `uv run pytest tests/flows/test_daily_run_golden.py -q` verde e `git diff --stat tests/fixtures/daily_run_golden.json` vazio.
- `tests/flows/test_daily_run_history.py` cobre os seis cenários de aceitação da US1 com `InMemoryHistoryStore`.
- `just daily-generate 1` (config dev) grava 1 registro, 1 snapshot `discovery`, 0 tentativas e 1 resumo `generate`; `just daily-publish-only output/daily` acrescenta 1 tentativa ao mesmo registro e 1 resumo `publish`.

### Implementação

- [X] T008 [US1] Em `src/flows/daily_run.py` adicionar os campos `history: HistoryStore` e `recipe: ProductionRecipe`; `generate`, `run` e `publish` chamam `history.start_run(mode=..., requested=..., started_at=self.now())` na primeira linha, acumulam `skipped: dict[SkipReason, int]` (`content_filter` e `script` em `_write`, `render` em `_produce`, `publish` no `except` de `run`, `not_needed` para candidatas sobrando ao atingir a meta) e fecham com `history.finish_run(run_id, RunSummary(...))` antes de cada `return`, inclusive quando `_find` falha (`stopped_reason="discovery_failed"`) ou não acha candidata (`"no_candidates"`); mensagens de progresso inalteradas
- [X] T009 [US1] Em `src/flows/daily_run.py::_produce`, após cada `save_manifest`, montar `VideoRecord` (run_id, video_path, title, summary, post_url, community, author, post_created_utc, part_index/part_count, language, `duration_seconds=None` até o M2, `grade=ModelGrade.from_evaluation(candidate.evaluation)`, `deterministic_score`, `recipe=self.recipe`) e `RedditSnapshot(source="discovery", taken_at=self.now(), score, num_comments, upvote_ratio, available=True)` a partir de `candidate.post`, chamar `history.add_video_record` e guardar o id junto do vídeo (`_produce` passa a devolver `list[tuple[GeneratedVideo, int]]` ou um dict `video_path -> record_id` que `run` consulta)
- [X] T010 [US1] Em `src/flows/daily_run.py::_schedule`, ao lado de cada `append_publish_log`, chamar `history.add_publish_attempt(record_id, PublishAttempt(attempted_at=self.now(), status, scheduled_at=slot, hashtags, publish_result, error))` com os mesmos valores da linha do CSV; em `publish` (publish-only) obter o `record_id` por `find_record_by_video_path(video.video_path)` e, ausente, criar um registro mínimo a partir do manifest com `add_video_record(record, None)` (`imported=True`, `run_id` da rodada atual)
- [X] T011 [US1] Em `src/core/container.py` passar `history=history_store` e `recipe=providers.Object(ProductionRecipe.empty())` ao provider `daily_run` (o M2 troca por `production_recipe`)
- [X] T012 [US1] Ajustar `tests/flows/test_daily_run_golden.py` para apontar `HISTORY_DB_PATH` ao `tmp_path` no fixture do container (o JSON golden **não muda**) e `tests/flows/test_daily_run.py`, `tests/flows/test_daily_run_shape.py` e `tests/flows/test_adapters.py` para construir `DailyRun` com `history=InMemoryHistoryStore()` e `recipe=ProductionRecipe.empty()`
  - Feito: golden com `HISTORY_DB_PATH` em `tmp_path` (JSON intocado); `build()` de `test_daily_run.py` recebe `history`/`recipe`. `test_adapters.py` não constrói `DailyRun` (usa `RecordingDailyRun`), sem mudança. `test_daily_run_shape.py`: teto de 300 → 320 linhas, justificado em plan.md Complexity Tracking (o fluxo avisa o histórico de cada evento; a contabilidade fica em `src/flows/run_record.py`).
- [X] T013 [US1] Criar `tests/flows/test_daily_run_history.py` com os fakes existentes (`FakeRedditProxy`, `FakeLLMProxy`, `FakeRenderer`, `FakePublisher`) e `InMemoryHistoryStore`: (1) rodada completa → 1 registro por vídeo com sinais, nota e tentativa; (2) história de 3 partes → 3 registros irmãos com `part_index` 1..3 e tentativas próprias; (3) primeira publicação falha e a segunda (publish-only) agenda → as duas tentativas no mesmo registro; (4) generate-only → registro sem tentativa, publish-only depois completa; (5) candidata bloqueada por filtro e outra com erro de render → fora do histórico e contadas em `skipped`; (6) `RunSummary` com `mode`, `requested`, `target`, `candidates_found`, `produced`, `scheduled`, `skipped`; (7) descoberta que estoura → resumo com `stopped_reason="discovery_failed"` e zero registros; (8) `add_video_record` que estoura derruba a rodada com a causa (princípio I)
- [X] T014 [US1] Verificação ao vivo do gate M1 pelo [quickstart §1](./quickstart.md): suíte verde, golden intocado, consultas `sqlite3` com os valores esperados após `just daily-generate 1` e `just daily-publish-only output/daily`
  - Evidência (2026-09-28, laptop): `uv run pytest -q` → 332 passed (linha de base 290 + 42 novos); `git diff --stat tests/fixtures/daily_run_golden.json` vazio; `src/flows/daily_run.py` com 311 linhas.
  - Evidência ao vivo: container real com `CONFIG_PATH=config.dev.yaml` (LLM mock, descoberta real no Reddit JSON, `SqliteHistoryStore` real em arquivo temporário), só renderer e publisher trocados por fakes — não se renderiza vídeo no laptop nem se publica no TikTok a partir dele. `generate(count=1)` e depois `publish(manifests)`; `sqlite3`: `video_records`=1; `reddit_snapshots` `discovery|1`; `run_summaries` `1|generate|requested 1|target 1|candidates 33|produced 1|scheduled 0|not_needed 32, demais 0` e `2|publish|1|1|0|0|1|todos 0`, ambas com `finished_at`; `publish_attempts` `1|scheduled|2026-09-28T21:00:00+00:00` (18:00 local, mesmo registro 1); registro com nota 87/Excelente, sub-notas, `hashtags` da tentativa.
  - Pendente do servidor: primeira rodada real (`just deploy` e a rodada diária seguinte) deixando `.storage/history.sqlite` no servidor.

**Checkpoint**: Milestone 1 DONE ✅

---

## Phase 4: Milestone 2 — Receita de produção e importação do passado (US4, US1) — PR 2

**Goal**: cada registro carrega a receita que o produziu (versão dos prompts,
modelos, estratégia, voz, taxa, duração) e o histórico do servidor entra uma vez
via importação idempotente do CSV e dos manifests.

**Independent test criteria**:
- Editar `src/prompts/story.jinja2` e gerar de novo produz registros com `story_prompt_version` diferentes e o resto da receita igual.
- `duration_seconds` > 0 nos registros novos; `voice_id` muda com o gênero resolvido.
- `just import-history` sobre uma cópia do CSV do servidor cria 1 tentativa por linha (inclusive linhas cujo mp4 não existe) e, rodado de novo, imprime "0 registros criados, 0 tentativas, N já existiam".

### Implementação

- [X] T015 [P] [US4] Em `src/prompts/loader.py` adicionar `fingerprint(name: str) -> str` (sha256 do arquivo `.jinja2`, 12 hex, arquivo ausente estoura); testar em `tests/prompts/test_loader.py` que o valor muda ao editar o template e é estável entre chamadas
- [X] T016 [P] [US4] Em `src/entities/rendered.py` adicionar `duration_seconds: float` a `RenderedPart`; em `src/capabilities/rendering/narration_over_footage.py` preenchê-lo com a duração do clipe composto (o que `VideoComposer.compose` devolve); atualizar `tests/fakes/renderer.py` e `tests/fakes/video.py` (`FakeComposer`) e afirmar `duration_seconds > 0` em `tests/capabilities/test_rendering.py`
- [X] T017 [P] [US4] Em `src/proxies/interfaces.py` adicionar `ISpeechProxy.voice_id(gender, language) -> str`; implementar em `src/proxies/edge_tts_proxy.py` e `src/proxies/elevenlabs_proxy.py` reutilizando a mesma resolução que `generate_speech` usa (config `voices[language]` ou o padrão do proxy); `FakeSpeechProxy` em `tests/fakes/proxies.py` devolve `fake-<gender>-<language>`; teste unitário para cada proxy real com config vazia e com config preenchida
  - Feito: `voice_id` público substitui o `_get_voice_id` privado dos dois proxies (o override continua só em `generate_speech`); testes em `tests/proxies/test_speech_voice_id.py`. A capacidade `rendering` reexporta `ISpeechProxy`, como `publishing` faz com o publisher.
- [X] T018 [US4] Criar `src/core/recipe.py` com `build_production_recipe(config: MainConfig) -> ProductionRecipe` (fingerprints de `story.jinja2` e `evaluate_story.jinja2`, `writer_model` = `provider/model` de `history_adaptation_llm_config` se houver senão `llm_config`, `"mock"` para `type: mock`, `grader_model` de `llm_config`, `rendering_strategy`, `speech_provider`, `speech_rate` = `default_rate` só no edge-tts, `language`; `narrator_gender` e `voice_id` vazios); provider `production_recipe = providers.Singleton(build_production_recipe, main_config)` em `src/core/container.py`, `daily_run` recebe `recipe=production_recipe` e `speech=speech_proxy`; cobrir em `tests/test_container_config.py` com os dois configs de exemplo
- [X] T019 [US4] Em `src/flows/daily_run.py` adicionar o campo `speech: Optional[ISpeechProxy] = None`; em `_produce`, `recipe = dataclasses.replace(self.recipe, narrator_gender=story.resolved_gender, voice_id=self.speech.voice_id(story.resolved_gender, story.language) if self.speech else "")` e `duration_seconds=part.duration_seconds`; estender `tests/flows/test_daily_run_history.py` com receita completa e voz diferente para histórias de gêneros diferentes
  - Feito: a receita por história é montada em `src/flows/run_record.py::RunRecord.video` (onde o M1 já monta o `VideoRecord`), não em `_produce`; o fluxo só passa `part.duration_seconds`. `daily_run.py` com 315 linhas.
- [X] T020 [US1] Criar `scripts/import_history.py` (`--csv CAMINHO` padrão `.storage/tiktok_publish_log.csv`, `--manifests DIR` repetível): agrupa linhas por `video_path`, cria `VideoRecord` mínimo (título, post_url, summary/part do manifest quando existir, `created_at` da primeira linha, `imported=True`) via `add_video_record(record, None)` quando `find_record_by_video_path` não acha, e uma `PublishAttempt` por linha cujo `attempted_at` ainda não está em `publish_attempts(record_id)`; não busca Reddit nem avalia; imprime "X registros criados, Y tentativas, Z já existiam"
  - Desvio: um vídeo é `(video_path, post_url)`, não só `video_path`: no servidor `output/daily/story_01.mp4` aparece em 96 vídeos diferentes. `find_record_by_video_path` ganhou `post_url=` opcional. Uma linha já existe quando o registro tem tentativa com o mesmo status a até 5 s (`SAME_ATTEMPT`): a rodada grava a linha do CSV e a tentativa em instantes seguidos, e o CSV corta os segundos. "Z já existiam" conta linhas (tentativas). O manifest só empresta resumo/parte se o `post_url` bater (o arquivo de hoje descreve outra história que a de ontem no mesmo caminho).
- [X] T021 [US1] Criar `tests/scripts/test_import_history.py` sobre um CSV de fixture com linhas reais e de pytest, um diretório de manifests com um mp4 presente e um ausente, e `SqliteHistoryStore` em `tmp_path`: registros e tentativas criados, mp4 ausente importado mesmo assim, `part` vindo do manifest, segunda execução sem duplicatas
- [X] T022 [US1] Em `Justfile` adicionar `import-history *args` (local) e `prod-import-history *args` (ssh no servidor com `CONFIG_PATH=config.prod.yaml`)
- [X] T023 [US4] Verificação ao vivo do gate M2 pelo [quickstart §2](./quickstart.md): receita e duração nos registros, versão do prompt muda ao editar, importação idempotente; `just prod-import-history` no servidor
  - Evidência (2026-09-28, laptop): `uv run pytest -q` → 360 passed; `git diff --stat main -- tests/fixtures/daily_run_golden.json` vazio.
  - Receita ao vivo: container real com `CONFIG_PATH=config.dev.yaml` (descoberta real, LLM mock, `EdgeTTSSpeechProxy` real para a voz, `SqliteHistoryStore` real), só o renderer trocado pelo fake (não se renderiza no laptop). Duas gerações no mesmo diretório, a segunda com `{# quickstart #}` no topo de `story.jinja2`: `1|42072ca8893c|673b96bf11d3|mock|mock|narration-over-footage|edge-tts|1.2|male|pt-BR-AntonioNeural` e `2|4ba6834641b4|…` com o resto igual. `duration_seconds` = 1.0 do renderer falso; a duração real (`video.clip.duration`) é coberta por `tests/capabilities/test_rendering.py` com o compositor falso — **não verificada sobre um mp4 real**.
  - Importação sobre cópia do CSV do servidor (449 linhas) e dos 10 manifests de `output/daily`: `444 registros criados, 449 tentativas, 0 já existiam` (379 `scheduled`, 70 `failed`, 3 linhas de pytest incluídas, 10 registros com resumo do manifest) em 2,7 s; segunda execução `0 registros criados, 0 tentativas, 449 já existiam`.
  - Pendente do servidor: `just deploy` (com o PR #12 e este) e `just prod-import-history`.

**Checkpoint**: Milestone 2 DONE ✅

---

## Phase 5: Milestone 3 — Leitor do TikTok Studio (US2) — PR 3

**Goal**: um proxy determinístico lê a lista de vídeos e a analytics por vídeo do
TikTok Studio com a sessão do servidor, sem agente de IA; os endpoints são
fixados por uma sondagem que também gera o fixture dos testes.

**Independent test criteria**:
- `just prod-tiktok-studio-probe` grava em `.storage/tiktok_studio_probe/<ts>/` ao menos uma resposta com a lista de vídeos e uma de analytics.
- `tests/fixtures/tiktok_studio_probe.json` está redigido e `uv run pytest tests/proxies/test_tiktok_studio_proxy.py -q` passa sem navegador.
- Sessão inválida → `TikTokSessionExpiredError`; campo ausente → `TikTokStudioLayoutError` nomeando o campo.

### Implementação

- [ ] T024 [US2] Criar `src/entities/configs/proxies/tiktok_studio.py` com `TikTokStudioConfig(user_data_dir: Optional[str] = None, headless: bool = False, lookback_days: int = 30, page_timeout_seconds: int = 60, max_gap_hours: int = 12)`; adicionar `tiktok_studio_config` a `ProxiesConfig` em `src/entities/config.py`; testar em `tests/test_container_config.py` que `user_data_dir` ausente deriva `<stem>_userdata` de `tiktok_publisher_config.cookies_path`
- [ ] T025 [US2] Criar `scripts/tiktok_studio_probe.py`: abre `patchright` com `launch_persistent_context(user_data_dir)` e injeta `Stealth().script_payload` (mesma sequência de `_start_session_with_stealth` em `src/proxies/tiktok_publisher_proxy.py`), registra `page.on("response")` e grava cada corpo JSON em `<out>/<ts>/NNN-<host>-<path>.json` (URL, status, corpo) mais `page-NN.png`; navega à lista de conteúdo do Studio, rola até o fim da primeira página, abre a analytics do primeiro vídeo; `--out` padrão `.storage/tiktok_studio_probe`; nunca parseia
- [ ] T026 [US2] Em `Justfile` adicionar `prod-tiktok-studio-probe` (ssh + `xvfb-run -a` como `prod-tiktok-publish`, seguido de `sync-tiktok-studio-probe`) e `sync-tiktok-studio-probe` (rsync do dump para o laptop); **rodar no servidor**, anotar em [research.md §2](./research.md) os endpoints e campos observados (lista, contagens, retenção) e gerar `tests/fixtures/tiktok_studio_probe.json` redigido (ids de conta, cookies e handles substituídos; ids de vídeo trocados por sequenciais) com uma resposta de lista e uma de analytics
- [ ] T027 [US2] Em `src/proxies/interfaces.py` adicionar `TikTokSessionExpiredError`, `TikTokStudioLayoutError` e `ITikTokStudioProxy` (`list_videos(*, since) -> list[TikTokVideoStats]`, `video_analytics(video_id) -> PerformanceMetrics`) conforme [contracts/performance-source.md](./contracts/performance-source.md)
- [ ] T028 [US2] Criar `src/proxies/tiktok_studio_proxy.py` com `PatchrightTikTokStudioProxy(user_data_dir, headless, page_timeout_seconds)`: constantes `CONTENT_LIST_URL`, `ANALYTICS_URL_TEMPLATE` e os padrões de URL das respostas (comentário apontando para `scripts/tiktok_studio_probe.py`), funções puras `_parse_video_list(body) -> list[TikTokVideoStats]` e `_parse_analytics(body) -> PerformanceMetrics` (campo esperado ausente → `TikTokStudioLayoutError("<campo> em <endpoint>")`), detecção de redirect para login → `TikTokSessionExpiredError`, rolagem até cobrir `since`, fechamento do contexto em `finally` com teto de 15 s como `_safe_stop`
- [ ] T029 [US2] Em `src/proxies/factories.py` adicionar `TikTokStudioProxyFactory.create(config, publisher_config)` (deriva `user_data_dir`); em `src/core/container.py` o provider `tiktok_studio_proxy = providers.Factory(...)`
- [ ] T030 [US2] Criar `tests/proxies/test_tiktok_studio_proxy.py`: `_parse_video_list` e `_parse_analytics` sobre o fixture devolvem os valores esperados (inclusive `saves`/retenção `None` quando ausentes de forma legítima), corpo sem o campo de contagem estoura nomeando o campo, URL de login detectada como sessão expirada; nenhum teste abre navegador
- [ ] T031 [US2] Verificação ao vivo do gate M3 pelo [quickstart §3](./quickstart.md): sondagem no servidor, fixture no PR, parser verde

**Checkpoint**: Milestone 3 DONE

---

## Phase 6: Milestone 4 — Coleta, casamento e atualização do Reddit (US2) — PR 4

**Goal**: um segundo fluxo lê o Studio, casa cada vídeo com seu registro pela
legenda e horário, grava snapshots datados de TikTok e Reddit em uma transação,
reporta não casados e ambíguos e aceita resolução manual; roda pela CLI e pelo bot.

**Independent test criteria**:
- `tests/capabilities/test_performance_matching.py` cobre as cinco regras do contrato.
- `tests/flows/test_collect_performance.py` cobre os seis cenários de aceitação da US2, a atomicidade (FR-014) e `assign`, sobre os dois stores.
- No servidor, `just prod-collect-performance 30` reporta "K casados, U sem par, A ambíguos" com K ≥ 95 % dos vídeos publicados pelo sistema; a segunda coleta dobra `performance_snapshots` sem alterar as linhas antigas; `/collect` recusa com rodada em andamento.

### Implementação

- [ ] T032 [P] [US2] Criar `src/capabilities/performance/__init__.py`, `contract.py` (`PerformanceSource` Protocol, `StudioPerformanceSource(proxy)` passa-adiante, `MatchResult`) e `matching.py` (`normalize_caption`, `match(records, videos, *, max_gap)`) com as regras 1–5 de [contracts/performance-source.md](./contracts/performance-source.md), sem I/O e sem `datetime.now()`
- [ ] T033 [P] [US2] Criar `tests/capabilities/test_performance_matching.py`: casamento por id já gravado, por legenda exata com hashtags finais e caixa diferente, desempate por horário dentro de `max_gap`, dois candidatos fora do gap → ambíguo, sem candidato → sem par, dois vídeos para o mesmo registro → ambos ambíguos
- [ ] T034 [P] [US2] Em `src/capabilities/discovery/contract.py` e `reddit_discovery.py` adicionar `signals(url) -> RedditSnapshot` (`source="collection"`, `taken_at=now`); em `src/proxies/interfaces.py` adicionar `RedditPostUnavailableError`, levantada por `src/proxies/json_reddit_proxy.py` e `src/proxies/reddit_proxy.py` em 404/403/post removido, mapeada para `available=False`; outros erros propagam; `FakeRedditProxy` em `tests/fakes/proxies.py` aceita um conjunto `unavailable_urls`; testes em `tests/capabilities/test_discovery.py` e `tests/test_json_reddit_proxy.py`
- [ ] T035 [US2] Estender `HistoryStore` em `src/storage/history_contract.py` com `published_records(since)`, `record_collection(collection, performance, reddit, assignments) -> int` (uma transação; falha em qualquer insert não deixa nada) e `assign_tiktok_video(record_id, tiktok_video_id)`; implementar em `src/storage/sqlite_history.py` e `tests/fakes/memory_history.py`; testar em `tests/storage/test_sqlite_history.py` (inclusive atomicidade com um `record_id` inexistente no meio da lista e `tiktok_video_id` duplicado estourando)
- [ ] T036 [US2] Criar `CollectionConfig(lookback_days, max_gap_hours)` em `src/entities/configs/flows.py` (a partir de `tiktok_studio_config`) e `src/flows/collect_performance.py` com `PerformanceCollection(source, discovery, history, config, progress, now)`: `collect(lookback_days=None) -> CollectionReport` na ordem de [contracts/flows-and-cli.md](./contracts/flows-and-cli.md) (fetch → published_records → match → metrics e signals por casado → `record_collection` único), linhas de progresso "🔎 N vídeos no Studio, M registros publicados" / "✅ K casados, U sem par, A ambíguos" / uma linha por não casado e ambíguo com legenda, data e ids candidatos; `assign(tiktok_video_id, record_id)`; qualquer exceção antes de `record_collection` propaga sem gravar
- [ ] T037 [P] [US2] Criar `tests/fakes/performance.py` com `FakePerformanceSource(videos, metrics_by_id, fail_fetch=False, fail_metrics_for=set())`
- [ ] T038 [US2] Criar `tests/flows/test_collect_performance.py` parametrizado sobre os dois stores, com histórico semeado por `DailyRun` ou diretamente: (1) vídeos publicados casam e ganham snapshot com os números e o `tiktok_video_id`; (2) segunda coleta acrescenta snapshots preservando os primeiros; (3) vídeo sem par listado no relatório e nada gravado; (4) `fail_fetch=True` estoura e o histórico fica idêntico; (5) duas legendas iguais fora do gap → ambíguo, nada gravado para elas; (6) cada casado ganha `RedditSnapshot(source="collection")` e post indisponível vira `available=False`; (7) `assign` grava o id e a coleta seguinte casa por id; (8) métrica ausente na analytics fica `None` sem falhar
- [ ] T039 [US2] Em `src/core/container.py` adicionar `performance_source = providers.Factory(StudioPerformanceSource, proxy=tiktok_studio_proxy)`, `collection_config = providers.Singleton(CollectionConfig.from_main_config, main_config)` e `performance_collection = providers.Factory(PerformanceCollection, source=..., discovery=story_discovery, history=history_store, config=collection_config)` (chamado com `progress=`)
- [ ] T040 [P] [US2] Criar `scripts/collect_performance.py` (`--lookback-days N` ou `--assign TIKTOK_ID RECORD_ID`, mutuamente exclusivos; progresso no stdout; saída 1 em falha) no mesmo molde de `scripts/daily_auto_publish.py`
- [ ] T041 [P] [US2] Em `bots/satisfying_bot.py` adicionar `/collect [dias]` que roda `container.performance_collection(progress=send_message).collect(lookback_days=...)` sob o `run_lock` existente (recusa com "Já existe um fluxo em andamento." quando ocupado) e registrar o `CommandHandler`; em `tests/flows/test_adapters.py` adicionar `RecordingCollection` e os casos bot e CLI chamando `collect` com os mesmos argumentos, e `--assign` chamando `assign`
- [ ] T042 [US2] Em `Justfile` adicionar `collect-performance *args` (local), `prod-collect-performance *args` (ssh + `xvfb-run -a` + `CONFIG_PATH=config.prod.yaml`, log em `.storage/tiktok_runs/<ts>-collect.log`, seguido de `sync-history`) e `sync-history` (rsync de `.storage/history.sqlite` e dos `-wal`/`-shm` se existirem, servidor → laptop, nunca o contrário); chamar `sync-history` também ao fim de `prod-daily-publish` e `prod-daily-publish-only`
- [ ] T043 [US2] Verificação ao vivo do gate M4 pelo [quickstart §4](./quickstart.md): testes verdes, duas coletas no servidor, um `--assign`, `/collect` pelo bot

**Checkpoint**: Milestone 4 DONE

---

## Phase 7: Milestone 5 — Visão cruzada, sincronização e docs (US3) — PR 5

**Goal**: um comando lista, ordena, filtra e exporta uma linha por vídeo com
Reddit (descoberta e agora), nota, receita e últimas métricas do TikTok; a
documentação descreve o histórico e a coleta.

**Independent test criteria**:
- `just report --sort grade_overall:desc` e `--sort latest_views` respondem SC-003 no laptop sobre o SQLite sincronizado, em < 10 s (SC-004).
- Vídeos sem snapshot aparecem com as colunas de desempenho vazias.
- `--csv` grava as mesmas linhas com todas as colunas; coluna inválida estoura listando as válidas.

### Implementação

- [ ] T044 [US3] Estender `HistoryStore` com `crossed_view(*, since, filters, sort) -> list[CrossedRow]` e a constante `CROSSED_COLUMNS` em `src/storage/history_contract.py`; implementar em `src/storage/sqlite_history.py` (consulta com subselects para o último `reddit_snapshots` por `source` e o último `performance_snapshots`; `filters`/`sort` validados contra `CROSSED_COLUMNS` antes de entrar no SQL, valores sempre por parâmetro) e em `tests/fakes/memory_history.py`; testar em `tests/storage/test_sqlite_history.py` com o mesmo cenário nos dois stores (linha sem snapshot presente com `None`, ordem por nota e por views, filtro por `story_prompt_version`, coluna inválida estoura nomeando as válidas)
- [ ] T045 [US3] Criar `scripts/performance_report.py` (`--since DATA`, `--sort COL[:desc]`, `--filter COL=VALOR` repetível, `--csv ARQUIVO`, `--columns`): usa só `container.history_store()`, imprime tabela alinhada com id, criado, título truncado a 40, nota, veredito, upvotes na descoberta, upvotes agora, views, likes, comentários, shares, saves, watch médio, % completo, `story_prompt_version` curto e `writer_model`; `--csv` grava todas as colunas de `CrossedRow`
- [ ] T046 [US3] Criar `tests/scripts/test_performance_report.py` sobre `SqliteHistoryStore` em `tmp_path` semeado: saída ordenada por nota decrescente mostra os de views baixas no topo (SC-003), linha sem snapshot presente com colunas vazias, CSV com o mesmo número de linhas e todas as colunas, `--columns` lista `CROSSED_COLUMNS`, coluna inválida sai com código 2 e a lista das válidas
- [ ] T047 [US3] Em `Justfile` adicionar `report *args` (`uv run python scripts/performance_report.py {{args}}`)
- [ ] T048 [US3] Verificação ao vivo do gate M5 pelo [quickstart §5](./quickstart.md): `just sync-history`, as quatro chamadas de `just report`, tempo < 10 s

**Checkpoint**: Milestone 5 DONE

---

## Phase 8: Polish & Cross-Cutting Concerns (dentro do PR 5)

- [ ] T049 [P] Atualizar `docs/architecture.md`: o segundo fluxo (`collect_performance`), a fronteira `HistoryStore` ao lado de `RunStore`, a capacidade `performance` e o proxy do Studio no diagrama e na tabela de contratos; árvore de `src/`, `scripts/` e `tests/` com os arquivos novos; seção "Extending" ganha "uma fonte de desempenho"
- [ ] T050 [P] Atualizar `docs/configuration.md`: seção `### TikTok Studio (tiktok_studio_config)` com as chaves e defaults, e `HISTORY_DB_PATH` na seção de variáveis de ambiente
- [ ] T051 [P] Atualizar `README.md` com a seção "Histórico e desempenho": o que é gravado, `just prod-import-history` (uma vez), quando rodar `just prod-collect-performance` (alguns dias após publicar, repetir para acompanhar), como resolver "sem par" com `--assign`, `just sync-history` e `just report`, e a restrição de não rodar coleta e publicação ao mesmo tempo
- [ ] T052 Adicionar o bloco comentado `tiktok_studio_config` a `config.yaml`, `config.prod.yaml` e `config.dev.yaml` e `HISTORY_DB_PATH` a `env.example`
- [ ] T053 Rodar `just fmt`, `uv run pytest -q` e a verificação final do [quickstart](./quickstart.md) (`git diff --stat main -- tests/fixtures/daily_run_golden.json` vazio; `grep -rn "sqlite3" src` só em `src/storage/sqlite_history.py`; `grep -rn "patchright" src` só em `src/proxies/`); registrar o resultado na seção Notes

---

## Dependencies & Execution Order

### Milestones

- **M1 (PR 1)** ← Setup. Fundação (T002–T007) antes de T008–T013.
- **M2 (PR 2)** ← M1 (o registro precisa existir para receber a receita e a importação).
- **M3 (PR 3)** ← M1 apenas pelo container; pode começar em paralelo com M2 se houver mãos. T026 exige o servidor e vem antes de T028–T030 (o parser é escrito contra o fixture).
- **M4 (PR 4)** ← M1 (registros publicados), M3 (proxy). T032–T034 e T037 independem de M3 e podem ser adiantados.
- **M5 (PR 5)** ← M4 (snapshots para cruzar). T049–T052 só dependem do desenho e podem ser escritos a qualquer momento após o M4 fechar.

### User Stories

- **US1** (M1 + importação no M2): sem dependência de outra story.
- **US4** (M2): depende de US1 (o registro existe).
- **US2** (M3 + M4): depende de US1 (registros para casar); independe de US4 e US3.
- **US3** (M5): depende de US1 e US2 (precisa de snapshots para cruzar; sem eles a tabela sai com colunas vazias, o que também é testável).

### Parallel Opportunities

- Fundação: T002, T003, T005 em paralelo; T004 depois de T002/T003; T006 depois de T004/T005.
- M2: T015, T016, T017 em paralelo; T018 depois de T015; T019 depois de T016–T018; T020–T022 independem de T015–T019.
- M3: T024 e T025 em paralelo; T026 no servidor; T027 em paralelo com T026; T028–T030 depois de T026.
- M4: T032, T033, T034, T037 em paralelo e antes de T035; T040 e T041 em paralelo depois de T036/T039.
- Polish: T049, T050, T051 em paralelo.

---

## Parallel Example: Milestone 4

```bash
# Antes do proxy do Studio existir (independem do M3):
Task: "T032 capabilities/performance: contract.py e matching.py"
Task: "T033 tests/capabilities/test_performance_matching.py"
Task: "T034 discovery.signals(url) + RedditPostUnavailableError"
Task: "T037 tests/fakes/performance.py"

# Depois do fluxo (T036) e do container (T039):
Task: "T040 scripts/collect_performance.py"
Task: "T041 bots/satisfying_bot.py /collect + test_adapters.py"
```

---

## Implementation Strategy

### MVP First (Milestone 1)

1. Setup (T001) e fundação (T002–T007).
2. M1 (T008–T014): a rodada passa a deixar registros. **Implantar**: cada dia sem
   isso é dado perdido, e nada muda para o operador.
3. Validar pelo quickstart §1 e abrir o PR 1.

### Incremental Delivery

1. M2: receita e importação do passado → PR 2 → `just prod-import-history`.
2. M3: sondagem no servidor primeiro; parser contra o fixture → PR 3.
3. M4: coleta → PR 4 → primeira `just prod-collect-performance` alguns dias após
   publicar com o M1 no ar.
4. M5: visão cruzada e docs → PR 5 → `just sync-history && just report`.

### O que não decompor

- Não dividir o M3 em "proxy" e "sondagem": o parser sem o fixture é chute, e o
  fixture sem o parser é arquivo morto.
- Não antecipar o M5 para dentro do M4: a visão cruzada sobre snapshots vazios é
  testável, mas o gate de SC-003 só faz sentido com coleta real no servidor.

---

## Notes

- Linha de base (T001): 290 passed, 0 falhas (`uv run pytest -q`, 2026-09-28, branch `005-video-performance-history`).
- Resultado final (T053): _preencher_.
- Desvios do M1 em relação ao desenho: `ModelGrade` não tem `summary` (o resumo já vive em `VideoRecord.summary`, e o esquema não tem coluna para ele); o contrato ganhou `HistoryError` (toda falha de escrita no SQLite) e `HistoryConflictError` (UNIQUE/FK), iguais nos dois stores, e as leituras `run_summary(run_id)` e `reddit_snapshots(record_id)`; a contabilidade da rodada fica em `src/flows/run_record.py` (`RunRecord` + `@recorded`), e o `except` de publicação do fluxo re-lança `HistoryError` em vez de tratá-la como falha de publicação (princípio I).
- Correção do M1 (PR #12, antes do M2): `video_path` deixou de ser `UNIQUE`. A rodada diária reescreve `output/daily/story_NN.mp4` todo dia, então a segunda rodada no servidor pararia com `HistoryConflictError`. A busca por caminho devolve o registro mais novo; um histórico criado com a restrição é reconstruído uma vez ao abrir.
- Golden: `tests/fixtures/daily_run_golden.json` não muda em nenhum PR (SC-006).
- Perfil do Chromium: coleta e publicação nunca ao mesmo tempo; o bot serializa
  pelo `run_lock`, a CLI estoura cedo se o perfil estiver em uso.
- Código, comentários e commits em inglês; este arquivo e as docs de spec em português.
