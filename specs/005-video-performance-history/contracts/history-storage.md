# Contrato de histórico — `src/storage/history_contract.py` (M1, M4, M5)

```python
class HistoryStore(Protocol):
    # M1 — rodada diária
    def start_run(self, *, mode: str, requested: int, started_at: datetime) -> int: ...
    def finish_run(self, run_id: int, summary: RunSummary) -> None: ...
    def add_video_record(
        self, record: VideoRecord, discovery_signals: RedditSnapshot | None
    ) -> int: ...
    def find_record_by_video_path(self, video_path: str) -> VideoRecord | None: ...
    def add_publish_attempt(self, record_id: int, attempt: PublishAttempt) -> None: ...

    # M4 — coleta
    def published_records(self, since: datetime) -> list[VideoRecord]: ...
    def record_collection(
        self,
        collection: Collection,
        performance: list[PerformanceSnapshot],
        reddit: list[RedditSnapshot],
        assignments: dict[int, str],          # record_id -> tiktok_video_id
    ) -> int: ...                             # tudo em uma transação
    def assign_tiktok_video(self, record_id: int, tiktok_video_id: str) -> None: ...

    # M5 — visão cruzada
    def crossed_view(
        self,
        *,
        since: datetime | None = None,
        filters: dict[str, str] | None = None,
        sort: tuple[str, bool] | None = None,   # (coluna, descendente)
    ) -> list[CrossedRow]: ...
```

Regras comuns às implementações:

- Toda escrita que falha **estoura** (princípio I). Não existe "log que não
  pode parar a rodada" aqui: sem registro, a rodada está errada.
- `start_run` grava a linha de `run_summaries` com contagens zero e devolve o
  id, que os registros da rodada carregam em `run_id`; `finish_run` completa a
  linha no fim. Uma rodada que estoura no meio deixa a linha com
  `finished_at` nulo, o que é a evidência de que ela não terminou.
- `add_video_record` recebe o snapshot da descoberta junto: na rodada ele
  sempre existe. `None` é para registros sem descoberta (importados pelo
  script, ou o registro mínimo que o publish-only cria a partir de um manifest
  de antes da feature); esses ficam com `imported=True`.
- `add_publish_attempt` com `(record_id, attempted_at)` repetido estoura
  (`UNIQUE`): a importação é idempotente porque verifica antes.
- `published_records(since)`: registros com ao menos uma tentativa `scheduled`
  cujo `scheduled_at >= since`, mais os que já têm `tiktok_video_id` (para
  continuar acumulando snapshots de vídeos antigos, dentro do mesmo `since`).
- `record_collection` grava a linha de `collections`, os snapshots e as
  atribuições de `tiktok_video_id` em uma transação; devolve o id da coleta.
- `crossed_view`: colunas válidas de `filters`/`sort` são as de `CrossedRow`;
  nome desconhecido estoura com a lista das válidas.

## `SqliteHistoryStore(path: str)` — `src/storage/sqlite_history.py`

- Abre com `sqlite3.connect(path, detect_types=0)`, `PRAGMA journal_mode=WAL`,
  `PRAGMA foreign_keys=ON`; cria o esquema de [data-model.md](../data-model.md)
  na construção. Diretório ausente é criado (é `.storage/`, já existe no
  servidor).
- Uma conexão por instância; o container expõe `history_store` como `Factory`
  para cada rodada ter a sua, lendo `HISTORY_DB_PATH` (padrão
  `.storage/history.sqlite`) na chamada.
- `crossed_view` é uma consulta com subselects para "último snapshot" por
  registro; `sort` e `filters` validados contra uma lista fixa de colunas antes
  de entrar no SQL (nunca interpolar entrada do usuário).
- Datas: `datetime.isoformat()` em UTC ao gravar; `datetime.fromisoformat` ao
  ler.

## `InMemoryHistoryStore` — `tests/fakes/memory_history.py`

Mesmo contrato sobre listas e dicionários; `crossed_view` em Python. Os testes
de fluxo (`test_daily_run_history.py`, `test_collect_performance.py`) rodam o
mesmo cenário contra os dois stores e esperam o mesmo resultado
(`tests/storage/test_sqlite_history.py` parametriza).

## Fora deste contrato, de propósito

- Manifests e CSV continuam no `RunStore`/`FileRunStore` (golden). A exclusão
  de posts já agendados continua vindo do CSV; mover para o SQLite é uma
  mudança futura que passaria pelo golden.
- Os mp4 não entram no banco; `video_path` aponta para eles.
