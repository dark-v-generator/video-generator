# Implementation Plan: Histórico de desempenho dos vídeos

**Branch**: `005-video-performance-history` (a criar a partir de `main`) | **Date**: 2026-09-28 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/005-video-performance-history/spec.md`

## Summary

Guardar, a cada rodada diária, um **registro por vídeo** (sinais do Reddit na
descoberta, nota do modelo com as cinco sub-notas, fatos do vídeo, **receita de
produção** e tentativas de publicação) e um **resumo por rodada**, em um banco
SQLite de arquivo único atrás de uma nova fronteira `HistoryStore`. Um segundo
fluxo, a **coleta de desempenho**, lê o TikTok Studio com a sessão que o servidor
já mantém, casa cada vídeo do TikTok com seu registro pela legenda e horário,
grava snapshots datados de métricas e, na mesma passada, atualiza os números do
Reddit. Um script produz a **visão cruzada** (tabela e CSV) sobre o SQLite, que o
laptop puxa do servidor com `just sync-history`.

Nada do que existe muda de comportamento: manifests, log CSV, exclusão de posts
já agendados e o teste golden da rodada continuam iguais. As escritas no
histórico são adições ao fluxo, atrás de contratos, com uma implementação em
memória nos testes.

## Technical Context

**Language/Version**: Python 3.12 (venv atual), `requires-python >= 3.11`.

**Primary Dependencies**: as atuais (pydantic, dependency-injector, jinja2,
litellm, patchright + playwright-stealth, python-telegram-bot). O banco usa
`sqlite3` da biblioteca padrão. **Nenhuma dependência nova.** O leitor do
TikTok Studio reaproveita `patchright` (já instalado no servidor pelo
`prod-tiktok-setup`) e o `user_data_dir` do publisher
(`.storage/tiktok_cookies_userdata/`), sem `browser-use` e sem LLM.

**Storage**: SQLite em `.storage/history.sqlite` (caminho via
`HISTORY_DB_PATH`, mesmo padrão de `TIKTOK_PUBLISH_LOG_PATH`), tabelas
`video_records`, `reddit_snapshots`, `publish_attempts`, `performance_snapshots`,
`run_summaries`, `collections`. Manifests JSON e `.storage/tiktok_publish_log.csv`
continuam sendo escritos pelo `FileRunStore`, sem alteração. Sincronização
servidor → laptop por rsync do arquivo `.sqlite` (somente leitura no laptop).

**Testing**: pytest sem rede e sem modelo, como hoje. Novo: `InMemoryHistoryStore`
em `tests/fakes/`, `FakePerformanceSource`, fixture JSON gravada da sondagem do
Studio (redigida), testes do SQLite sobre arquivo temporário, golden inalterado.

**Target Platform**: Linux (servidor: bot via systemd sob `xvfb-run`; coleta roda
lá porque é onde a sessão do TikTok vive) e macOS (laptop: visão cruzada sobre o
SQLite sincronizado, testes).

**Project Type**: projeto único, Clean Architecture em módulos (feature 004).

**Performance Goals**: SC-004: visão cruzada do histórico inteiro em < 10 s (com
3 vídeos/dia são ~1 000 registros/ano; uma consulta SQL resolve). Coleta: uma
navegação ao Studio mais uma página de analytics por vídeo publicado nos últimos
N dias (padrão 30), dentro de um minuto por vídeo.

**Constraints**: SC-006 golden inalterado; FR-019 escrita só pela fronteira;
FR-014 coleta atômica (transação: ou grava tudo ou nada); o Chromium do Studio
e o do publisher usam o mesmo perfil e **não podem rodar ao mesmo tempo** (o bot
serializa pelo `RunLock`; na linha de comando o lançamento falha cedo se o perfil
estiver em uso). Princípio I: falhas de escrita no histórico derrubam a rodada
com a causa.

**Scale/Scope**: 1 operador, 3 vídeos/dia, ~150 linhas de log existentes no
servidor para importar. 5 PRs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação | Resultado |
|-----------|-----------|-----------|
| I. Fail Fast e Simplicidade | Escrita no histórico que falha estoura a rodada com a causa (não há "log que não pode parar a rodada" como no CSV, porque aqui o registro é o produto). Coleta é uma transação: sessão expirada, layout do Studio mudado ou endpoint ausente estouram com a causa e nada é gravado. Casamento ambíguo não é resolvido por heurística extra: é reportado e resolvido à mão. Nenhum retry novo. Métrica que o Studio não expõe fica `NULL`, sem ramo defensivo. | PASS |
| II. Arquitetura Limpa em Módulos | Entidades novas sem I/O em `src/entities/history.py`. Fronteira nova `HistoryStore` (Protocol) em `src/storage/history_contract.py`, com `SqliteHistoryStore` e `InMemoryHistoryStore`. Capacidade nova `src/capabilities/performance/` com o contrato `PerformanceSource` e a lógica pura de casamento; o acesso ao Studio é um proxy (`src/proxies/tiktok_studio_proxy.py`) atrás de `ITikTokStudioProxy`. Dois fluxos finos (`daily_run` estendido, `collect_performance` novo) dependem só de contratos. Adaptadores (bot, CLI) só traduzem comandos. Dependências apontam para dentro. | PASS |
| III. Prompts Baseados em Racional | Nenhum prompt novo e nenhum prompt alterado; o fingerprint só lê o arquivo. | PASS |
| Idioma | Plano, research, data-model, contracts e quickstart em português; código, comentários, commits e nomes de arquivos em inglês. `spec.md` em inglês, acompanhando o pedido do usuário (mesmo desvio documentado nas features 002 a 004). | PASS (desvio documentado) |

**Re-check pós-design (Phase 1)**: o desenho final acrescenta uma segunda
fronteira de armazenamento em vez de estender `RunStore`. Justificado em
Complexity Tracking: `RunStore` continua sendo "o que o publish-only e a exclusão
leem hoje" (arquivos), e `HistoryStore` é "o que a análise lê" (banco); fundir os
dois obrigaria o golden a mudar ou o SQLite a reproduzir o CSV. O proxy do Studio
conhece `patchright` e o layout do `user_data_dir` do publisher, mas fica na
borda; a capacidade e o fluxo só veem `TikTokVideoStats`. PASS.

## Delivery Plan

5 milestones, 1 PR cada. Ordem: primeiro o registro (para começar a acumular
dados o quanto antes), depois a receita e a importação do passado, depois o
leitor do Studio (o único passo com incerteza externa, isolado em seu PR com uma
sondagem no servidor), depois o fluxo de coleta, por fim a visão cruzada e a
documentação. A rodada diária continua implantável ao fim de cada PR.

### M1 — Registro por vídeo e por rodada (US1) — PR 1

- `src/entities/history.py`: `RedditSnapshot`, `ModelGrade`, `ProductionRecipe`
  (só a forma; preenchida no M2), `PublishAttempt`, `PerformanceSnapshot`,
  `VideoRecord`, `RunSummary`, `SkipReason`, `CollectionReport`, `TikTokVideoStats`
  ([data-model.md](./data-model.md)).
- `src/storage/history_contract.py`: `HistoryStore` (Protocol) com
  `start_run`/`finish_run`, `add_video_record`, `add_publish_attempt`, e
  leituras ([contracts/history-storage.md](./contracts/history-storage.md)).
- `src/storage/sqlite_history.py`: `SqliteHistoryStore(path)` cria o esquema na
  primeira abertura (`CREATE TABLE IF NOT EXISTS`), uma transação por método.
- `tests/fakes/memory_history.py`: `InMemoryHistoryStore`.
- `src/flows/daily_run.py`: recebe `history: HistoryStore` e `recipe:
  ProductionRecipe`; em `_produce`, após cada `save_manifest`, cria o
  `VideoRecord` (sinais do Reddit e nota vêm do `EvaluatedStory` já em mãos;
  `duration_seconds` vem do `RenderedPart`, ver M2; até lá `None`); em
  `_schedule`, registra o `PublishAttempt` ao lado do `append_publish_log`;
  `generate`, `run` e `publish` abrem a rodada com `start_run`, contam pulos
  por motivo e fecham com `finish_run` (inclusive quando a busca falha ou não
  acha candidata). `publish` (publish-only) encontra o registro pelo
  `video_path` do manifest e acrescenta a tentativa; sem registro (vídeo de
  antes da feature) cria um registro mínimo a partir do manifest, sem snapshot
  de descoberta e com `imported=True`, como a importação faria.
- `src/core/container.py`: provider `history_store` (Factory, lê `HISTORY_DB_PATH`
  a cada chamada) e `production_recipe` (M2; no M1 um recipe vazio); `daily_run`
  recebe ambos.
- Golden: passa a apontar `HISTORY_DB_PATH` para o diretório temporário; o
  fixture **não muda**. Teste novo `tests/flows/test_daily_run_history.py` com o
  store em memória: 1 registro por vídeo, N por história em N partes, tentativa
  falha preservada e sucesso posterior no mesmo registro, resumo da rodada com
  contagens e motivos, generate-only sem tentativa.
- `tests/storage/test_sqlite_history.py`: mesmo cenário contra o SQLite em
  arquivo temporário, esquema criado do zero, escrita que falha estoura.

**Gate**: `uv run pytest -q` verde com golden intocado; `just daily-generate 1`
com `config.dev.yaml` deixa `.storage/history.sqlite` com 1 `video_records`, 1
`reddit_snapshots` (origem `discovery`), 0 `publish_attempts`, 1 `run_summaries`.

### M2 — Receita de produção e importação do passado (US4, FR-017) — PR 2

- `src/prompts/loader.py`: `fingerprint(name) -> str` (sha256 do arquivo,
  12 hex). `src/entities/rendered.py`: `RenderedPart.duration_seconds: float`,
  preenchido pelo `NarrationOverFootageRenderer` a partir do clipe composto
  (`FakeRenderer` e `FakeComposer` acompanham).
- `src/proxies/interfaces.py`: `ISpeechProxy.voice_id(gender, language) -> str`
  (o id que `generate_speech` usaria); implementado em edge-tts, ElevenLabs e
  no fake.
- `src/core/container.py`: `production_recipe` monta `ProductionRecipe` a partir
  de `MainConfig`, dos fingerprints (`story.jinja2`, `evaluate_story.jinja2`),
  do modelo do escritor (`history_adaptation_llm_config` se houver, senão
  `llm_config`), do modelo do avaliador (`llm_config`), de
  `rendering_strategy`, do tipo de fala e de `default_rate` (edge-tts). A voz
  depende do gênero resolvido, então `DailyRun` completa `voice_id` por história
  via `speech_proxy.voice_id`; o resto da receita é fixo por processo.
- `scripts/import_history.py`: lê `.storage/tiktok_publish_log.csv` e os
  manifests de um ou mais diretórios; cria `video_records` mínimos (título,
  post_url, parte, `imported=True`) e `publish_attempts` por linha; idempotente
  (chave natural `video_path + created_at`); não busca Reddit nem avalia. Receita
  `just import-history` e `just prod-import-history`.
- Testes: fingerprint muda ao editar o template; receita reflete config;
  importação sobre uma cópia do CSV do servidor e sobre linhas de teste
  (arquivos ausentes viram tentativas mesmo assim, FR-017 edge case).

**Gate**: editar `src/prompts/story.jinja2`, gerar de novo, e os dois registros
têm `story_prompt_version` diferentes e o resto igual; `just import-history`
sobre o CSV do servidor termina com o número de linhas do CSV em
`publish_attempts` e roda duas vezes sem duplicar.

### M3 — Leitor do TikTok Studio (parte de US2) — PR 3

- `scripts/tiktok_studio_probe.py`: abre o Chromium `patchright` com o
  `user_data_dir` do publisher (mesma injeção de stealth do
  `_start_session_with_stealth`), navega até o Studio (lista de conteúdo e a
  analytics de um vídeo), grava em `.storage/tiktok_studio_probe/` cada resposta
  JSON interceptada (URL, status, corpo) e um screenshot. Roda no servidor com
  `just prod-tiktok-studio-probe`. **Primeira tarefa do milestone**: fixa os
  endpoints e os nomes dos campos de [research.md §2](./research.md) e gera o
  fixture redigido `tests/fixtures/tiktok_studio_probe.json`.
- `src/proxies/interfaces.py`: `ITikTokStudioProxy.list_videos(since) ->
  list[TikTokVideoStats]` e `video_analytics(video_id) -> PerformanceMetrics`.
- `src/proxies/tiktok_studio_proxy.py`: `PatchrightTikTokStudioProxy(user_data_dir,
  headless)`: sessão persistente, intercepta as respostas, extrai
  `id`, `desc`, `create_time`, views, likes, comments, shares, saves; por vídeo,
  tempo médio assistido e % que viu até o fim quando a analytics os devolve. Sem
  sessão válida (redirect para login) estoura `TikTokSessionExpiredError`;
  resposta sem os campos esperados estoura nomeando o campo (layout mudou).
- `src/entities/configs/proxies/tiktok_studio.py` +
  `proxies.tiktok_studio_config` em `MainConfig` (`user_data_dir` deriva de
  `tiktok_publisher_config.cookies_path` por padrão, `headless`,
  `lookback_days`).
- Testes: parser sobre o fixture (sem navegador); erro de sessão e de campo.

**Gate**: `just prod-tiktok-studio-probe` produz o dump no servidor e o fixture
está no PR; `uv run pytest tests/proxies/test_tiktok_studio_proxy.py -q` verde.

### M4 — Fluxo de coleta, casamento e atualização do Reddit (US2) — PR 4

- `src/capabilities/performance/contract.py`: `PerformanceSource` (Protocol);
  `matching.py`: `match(records, tiktok_videos) -> MatchResult` (puro:
  normaliza legenda, compara com o título publicado, desempata por horário
  agendado, classifica `matched` / `unmatched` / `ambiguous`; registro com
  `tiktok_video_id` já gravado casa direto).
- `src/capabilities/discovery/contract.py`: `signals(url) -> RedditSnapshot`
  (usa `get_reddit_post`; post removido → snapshot `available=False`).
- `src/flows/collect_performance.py`: `PerformanceCollection(source, discovery,
  history, config, progress)`: lê os vídeos do Studio dos últimos
  `lookback_days`, casa com os registros publicados, para cada casado busca a
  analytics do vídeo e o snapshot do Reddit, e grava **tudo em uma transação**
  (`history.record_collection(report, snapshots)`); devolve o
  `CollectionReport`. `assign(tiktok_video_id, record_id)` para a resolução
  manual (FR-012).
- Adaptadores: `scripts/collect_performance.py` (`--lookback-days`,
  `--assign TIKTOK_ID RECORD_ID`, progresso no stdout); bot: `/collect` sob o
  mesmo `RunLock` da rodada (o publisher e o Studio compartilham o perfil do
  Chromium). `tests/flows/test_adapters.py` ganha os dois casos.
- `Justfile`: `collect-performance` (local, exige sessão; documentado como
  server-only na prática), `prod-collect-performance` (xvfb-run, como
  `prod-daily-publish`), e `sync-history` (rsync do `.sqlite` para o laptop),
  chamado ao fim de `prod-collect-performance` e de `prod-daily-publish`.
- Testes: casamento (exato, por horário, ambíguo, sem par, id já conhecido);
  fluxo com `FakePerformanceSource` e store em memória: snapshots datados e
  preservados entre duas coletas, Reddit atualizado, relatório com não casados,
  falha do source deixa o histórico intacto; resolução manual.

**Gate**: `uv run pytest tests/capabilities/test_performance_matching.py
tests/flows/test_collect_performance.py -q` verde; no servidor,
`just prod-collect-performance` termina com "N casados, M sem par" e
`performance_snapshots` ganha N linhas.

### M5 — Visão cruzada, sincronização e documentação (US3) — PR 5

- `src/storage/history_contract.py`: `crossed_view(filters, sort) ->
  list[CrossedRow]` (uma linha por vídeo: registro + snapshot do Reddit da
  descoberta + último snapshot do Reddit + último de desempenho + receita),
  implementado em SQL no `SqliteHistoryStore` e em Python no fake.
- `scripts/performance_report.py`: tabela no terminal, `--sort COL[:desc]`,
  `--filter COL=VALOR` (repetível; inclui `story_prompt_version`), `--csv
  ARQUIVO`, `--since DATA`. Lê `HISTORY_DB_PATH`; roda no laptop sobre o
  arquivo puxado por `just sync-history`. Receita `just report`.
- Docs: `docs/architecture.md` (segundo fluxo, fronteira `HistoryStore`,
  capacidade `performance`), `docs/configuration.md` (`tiktok_studio_config`,
  `HISTORY_DB_PATH`), `README.md` (seção "Histórico e desempenho": comandos,
  quando rodar a coleta, como resolver não casados).
- Testes: `crossed_view` no SQLite e no fake com o mesmo cenário; script com
  `--csv` gera as mesmas linhas.

**Gate**: SC-003 e SC-004 pelo [quickstart §5](./quickstart.md); suíte verde;
docs sem referência a comportamento que não existe.

## Project Structure

### Documentation (this feature)

```text
specs/005-video-performance-history/
├── plan.md              # este arquivo
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1: validação por milestone
├── contracts/
│   ├── history-storage.md     # HistoryStore, SqliteHistoryStore, InMemoryHistoryStore
│   ├── performance-source.md  # ITikTokStudioProxy, PerformanceSource, matching
│   └── flows-and-cli.md       # PerformanceCollection, DailyRun (mudanças), scripts, bot, Justfile
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
src/
├── entities/
│   ├── history.py                 # NOVO (M1): VideoRecord, RunSummary, snapshots, receita
│   ├── rendered.py                # M2: + duration_seconds
│   └── configs/proxies/tiktok_studio.py   # NOVO (M3)
├── prompts/loader.py              # M2: + fingerprint(name)
├── proxies/
│   ├── interfaces.py              # M2: ISpeechProxy.voice_id; M3: ITikTokStudioProxy
│   ├── edge_tts_proxy.py, elevenlabs_proxy.py   # M2: voice_id
│   ├── tiktok_studio_proxy.py     # NOVO (M3): PatchrightTikTokStudioProxy
│   └── factories.py               # M3: TikTokStudioProxyFactory
├── capabilities/
│   ├── discovery/contract.py, reddit_discovery.py   # M4: signals(url)
│   └── performance/               # NOVO (M4)
│       ├── __init__.py
│       ├── contract.py            # PerformanceSource, MatchResult
│       └── matching.py            # match(): lógica pura
├── storage/
│   ├── history_contract.py        # NOVO (M1): HistoryStore; M5: crossed_view
│   └── sqlite_history.py          # NOVO (M1): SqliteHistoryStore
├── flows/
│   ├── daily_run.py               # M1: grava registros, tentativas, resumo; M2: voz na receita
│   └── collect_performance.py     # NOVO (M4): PerformanceCollection
└── core/container.py              # M1: history_store; M2: production_recipe; M3: tiktok_studio_proxy; M4: performance_collection
bots/satisfying_bot.py             # M4: /collect
scripts/
├── import_history.py              # NOVO (M2)
├── tiktok_studio_probe.py         # NOVO (M3)
├── collect_performance.py         # NOVO (M4)
└── performance_report.py          # NOVO (M5)
tests/
├── fakes/memory_history.py        # NOVO (M1)
├── fakes/performance.py           # NOVO (M4): FakePerformanceSource
├── fixtures/tiktok_studio_probe.json   # NOVO (M3), redigido
├── flows/test_daily_run_history.py, test_collect_performance.py
├── storage/test_sqlite_history.py
├── capabilities/test_performance_matching.py
├── proxies/test_tiktok_studio_proxy.py
├── prompts/test_loader.py         # M2: fingerprint
└── scripts/test_import_history.py, test_performance_report.py
Justfile                           # M2: import-history; M4: collect-performance, prod-collect-performance, sync-history; M5: report
docs/architecture.md, docs/configuration.md, README.md   # M5
```

**Structure Decision**: projeto único, mesma disposição da feature 004. O
histórico entra como segunda fronteira em `src/storage/`, a leitura do Studio
como proxy na borda e uma capacidade fina de casamento, a coleta como segundo
fluxo em `src/flows/`, e três scripts novos como adaptadores.

## Verificação pós-implementação

- Golden (`tests/flows/test_daily_run_golden.py`) intocado em todos os PRs
  (SC-006).
- `uv run pytest -q` verde; nenhum teste depende de rede, de modelo ou do
  Chromium (o proxy do Studio é testado sobre o fixture).
- `grep -rn "sqlite3" src/` só em `src/storage/sqlite_history.py`;
  `grep -rn "patchright" src/` só em `src/proxies/` (fronteiras respeitadas).
- Sequência real no servidor: `just deploy`, `just prod-import-history`,
  rodada diária normal, dias depois `just prod-collect-performance`,
  `just sync-history`, `just report --sort views:desc` no laptop.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Segunda fronteira de armazenamento (`HistoryStore` ao lado de `RunStore`) | `RunStore` define o que o publish-only e a exclusão leem hoje, em arquivos com formato fixo pelo golden; o histórico é um modelo relacional consultável | Estender `RunStore` obrigaria o `FileRunStore` a implementar o histórico em arquivos ou o SQLite a reproduzir CSV e manifests; fundir os dois quebraria o golden ou duplicaria o formato |
| `RenderedPart.duration_seconds` e `ISpeechProxy.voice_id` (duas interfaces existentes mudam) | A duração e a voz efetiva só são conhecidas por quem renderiza e por quem fala; o registro precisa das duas (FR-004, FR-005) | Medir a duração pelo mp4 no fluxo traria moviepy para o fluxo; deduzir a voz da config no container duplicaria a regra de resolução do proxy |
| Script de sondagem do Studio (`tiktok_studio_probe.py`) mantido no repositório | O layout e os endpoints do Studio não são estáveis nem verificáveis fora do servidor; a sondagem é como se regrava o fixture quando o parser quebra | Fixar os endpoints só no research deixaria o próximo quebra-galho sem ferramenta; um teste "ao vivo" exigiria sessão no CI |
| Teto de `src/flows/daily_run.py` de 300 para 320 linhas (SC-009 da feature 004) | O fluxo passa a avisar o histórico de cada evento (abrir/fechar a rodada, pulo por motivo, vídeo, tentativa): uma linha por evento, ~14 no total; a contabilidade e a montagem das entidades ficam em `src/flows/run_record.py` (`RunRecord`, `@recorded`) | Espremer o código existente para caber em 300 pioraria a leitura que o SC-009 protege; esconder os eventos em um wrapper de `Progress` ou do `RunStore` tiraria do fluxo a decisão de por que cada história foi pulada |
