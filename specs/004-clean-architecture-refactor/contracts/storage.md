# Contrato de armazenamento — `src/storage/contract.py` (M6)

```python
@dataclass
class PublishLogEntry:
    status: Literal["scheduled", "failed"]
    scheduled_at: datetime | None
    video: GeneratedVideo
    hashtags: list[str]
    publish_result: str = ""
    error: str = ""

class RunStore(Protocol):
    def save_manifest(self, video: GeneratedVideo, output_dir: str) -> str: ...
    def load_manifests(self, output_dir: str) -> list[GeneratedVideo]: ...
    def append_publish_log(self, entry: PublishLogEntry) -> None: ...
    def scheduled_post_urls(self) -> set[str]: ...
```

## `FileRunStore(publish_log_path: str)` — `src/storage/files.py`

Reproduz o que o bot faz hoje, byte a byte:

- `save_manifest`: `{output_dir}/{basename(video_path)}.json` com
  `video_path`, `title`, `summary`, `post_url`, `source` e, só quando não é
  `None`, `part`; `ensure_ascii=False`, `indent=2`.
- `load_manifests`: lê os `.json` do diretório em ordem de nome, resolve
  `video_path` relativo ao diretório, pula (com warning) os que não têm o mp4,
  `source` ausente → `"auto"`, `part` ausente → `None`. Manifests escritos antes
  da refatoração carregam (FR-019).
- `append_publish_log`: CSV com cabeçalho na primeira escrita, colunas
  `created_at, status, scheduled_at, video_path, title, post_url, hashtags,
  publish_result, error`; `created_at` = agora em ISO com segundos;
  `scheduled_at` em ISO com minutos ou vazio; `hashtags` como `#a #b`. Falha de
  escrita é logada e não derruba a rodada (comportamento atual).
- `scheduled_post_urls`: `post_url` das linhas com `status == "scheduled"`;
  arquivo ausente → conjunto vazio.
- Caminho do log: argumento do construtor; o container passa
  `os.environ.get("TIKTOK_PUBLISH_LOG_PATH", ".storage/tiktok_publish_log.csv")`.

## `InMemoryRunStore` — `tests/fakes/memory_store.py`

Mesmo contrato sobre dicionários e listas; `manifests[dir][basename]` e
`log: list[PublishLogEntry]`. Serve aos testes do fluxo (SC-006) e é o
esqueleto do que uma implementação em banco terá de fazer.

## Fora deste contrato, de propósito

- Candidatas descobertas: a rodada diária não as persiste hoje; adicionar um
  método `record_candidates` é o passo natural quando a interface web existir
  (FR-016 lista o que ela vai perguntar: o que foi produzido, publicado, quando,
  e o que falhou e por quê; os três primeiros já são respondidos por
  `load_manifests` e pelo log, o último pelo log com `status=failed`).
- Vídeos em si: o fluxo grava o mp4 diretamente em `output_dir` (é um arquivo
  grande, não um registro), e o store guarda o caminho.
