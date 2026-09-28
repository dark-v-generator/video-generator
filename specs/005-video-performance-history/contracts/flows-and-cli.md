# Fluxos e adaptadores (M1, M2, M4, M5)

## `DailyRun` — mudanças (M1, M2)

```python
@dataclass(kw_only=True)
class DailyRun:
    ...                                  # campos atuais inalterados
    history: HistoryStore                # M1
    recipe: ProductionRecipe             # M2 (M1: ProductionRecipe.empty())
    speech: ISpeechProxy | None = None   # M2: voice_id por história
```

- `generate`/`run`/`publish`: mesmas assinaturas e mesmas mensagens de
  progresso (golden). Cada um abre a rodada com `history.start_run(...)` na
  primeira linha, conta pulos por motivo e fecha com `history.finish_run(run_id,
  summary)` no fim, inclusive quando `_find` falha ou não acha candidata
  (`stopped_reason`).
- `_produce`: após cada `save_manifest`, `history.add_video_record(record,
  discovery_snapshot)` com `record.run_id` = o id devolvido por `start_run`.
- `_schedule`: ao lado de cada `append_publish_log`, `history.add_publish_attempt(
  record_id, attempt)` com os mesmos valores da linha do CSV. Em `publish`
  (publish-only), o `record_id` vem de `find_record_by_video_path`; ausente,
  cria um registro mínimo a partir do manifest (`imported=True`).
- A ordem "manifest, depois registro" garante que uma falha do histórico deixa
  o manifest no disco (o vídeo existe) e estoura a rodada com a causa.

## `PerformanceCollection` — `src/flows/collect_performance.py` (M4)

```python
@dataclass(kw_only=True)
class PerformanceCollection:
    source: PerformanceSource
    discovery: StoryDiscovery
    history: HistoryStore
    config: CollectionConfig         # lookback_days, max_gap_hours
    progress: Progress
    now: Callable[[], datetime] = datetime.now

    async def collect(self, *, lookback_days: int | None = None) -> CollectionReport: ...
    def assign(self, tiktok_video_id: str, record_id: int) -> None: ...
```

`collect`, top a baixo: `since = now - lookback`; `videos = source.fetch(since)`;
`records = history.published_records(since)`; `result = match(records, videos)`;
para cada casado, `source.metrics(video_id)` e `discovery.signals(post_url)`;
monta os snapshots; `history.record_collection(...)` em uma transação; progresso:
"🔎 N vídeos no Studio, M registros publicados", "✅ K casados, U sem par, A
ambíguos", e uma linha por não casado/ambíguo com legenda e data. Qualquer
exceção antes de `record_collection` sai sem gravar (FR-014).

## Scripts

- `scripts/collect_performance.py` (M4): `[--lookback-days N] | --assign
  TIKTOK_ID RECORD_ID`; progresso no stdout; código de saída 1 em falha.
- `scripts/performance_report.py` (M5): `[--since DATA] [--sort COL[:desc]]
  [--filter COL=VALOR]... [--csv ARQUIVO]`; imprime tabela alinhada com as
  colunas principais (id, criado, título truncado, nota, veredito, upvotes na
  descoberta, upvotes agora, views, likes, comentários, shares, saves, watch
  médio, % completo, prompt, modelo); `--csv` grava todas as colunas de
  `CrossedRow`; `--columns` lista as colunas válidas.
- `scripts/import_history.py` (M2): `[--csv CAMINHO] [--manifests DIR]...`;
  imprime "X registros criados, Y tentativas, Z já existiam".
- `scripts/tiktok_studio_probe.py` (M3): sem argumentos além de `--out`.

Todos leem o container (`container.history_store()`, etc.), exceto
`performance_report`, que abre `SqliteHistoryStore(history_db_path())`
(`src/core/paths.py`) sem importar o container: roda no laptop sem chaves, e
importar o container custa ~7 s (o `litellm` baixa a tabela de preços a cada
import), o que deixaria SC-004 na margem.

## Bot (M4)

`/collect [dias]` → `container.performance_collection(progress=send_message)
.collect(lookback_days=...)` sob o `run_lock` existente (perfil do Chromium
compartilhado com o publisher); ocupado → "Já existe um fluxo em andamento.".
`tests/flows/test_adapters.py` cobre bot e CLI chamando o mesmo método com os
mesmos argumentos.

## Justfile

| Receita | Faz |
|---------|-----|
| `import-history` / `prod-import-history` (M2) | roda `import_history.py` local / no servidor |
| `prod-tiktok-studio-probe` + `sync-tiktok-studio-probe` (M3) | sondagem no servidor sob xvfb e cópia do dump para o laptop |
| `collect-performance [dias]` / `prod-collect-performance [dias]` (M4) | coleta; a prod chama `sync-history` no fim |
| `sync-history` (M4) | `rsync` de `.storage/history.sqlite` (e `-wal`/`-shm` se existirem) servidor → laptop; também chamado ao fim de `prod-daily-publish` |
| `report *args` (M5) | `performance_report.py` sobre `HISTORY_DB_PATH` local |

## Container (M1–M4)

```python
history_store = providers.Factory(SqliteHistoryStore, path=providers.Callable(_history_db_path))
production_recipe = providers.Singleton(build_recipe, main_config, prompts_module=prompts)   # M2
tiktok_studio_proxy = providers.Factory(TikTokStudioProxyFactory.create, config=..., publisher_config=...)  # M3
performance_source = providers.Factory(StudioPerformanceSource, proxy=tiktok_studio_proxy)    # M4
performance_collection = providers.Factory(PerformanceCollection, source=..., discovery=story_discovery,
                                           history=history_store, config=collection_config)   # M4
```

`_history_db_path()` lê `HISTORY_DB_PATH` a cada chamada (golden e testes
apontam para um diretório temporário).
