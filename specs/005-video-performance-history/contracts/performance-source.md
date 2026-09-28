# Contratos de desempenho — proxy do Studio, fonte e casamento (M3, M4)

## `ITikTokStudioProxy` — `src/proxies/interfaces.py` (M3)

```python
class TikTokSessionExpiredError(RuntimeError): ...
class TikTokStudioLayoutError(RuntimeError): ...   # campo/endpoint esperado ausente

class ITikTokStudioProxy(ABC):
    async def list_videos(self, *, since: datetime) -> list[TikTokVideoStats]: ...
    async def video_analytics(self, video_id: str) -> PerformanceMetrics: ...
    async def close(self) -> None: ...          # também `async with proxy:`
```

- Um navegador serve todas as chamadas até `close` (ou o fim do `async with`):
  a coleta abre o perfil uma vez, não uma vez por vídeo.

- `list_videos`: os posts da conta com `created_at >= since`, com id, legenda
  (`desc`), data e as contagens da lista (views, likes, comments, shares,
  saves). Lista vazia é uma resposta válida.
- `video_analytics`: tempo médio assistido e fração que viu até o fim; campo
  que a analytics não devolve fica `None`.
- Redirecionamento para login ou página sem sessão → `TikTokSessionExpiredError`.
  Resposta interceptada sem o campo esperado → `TikTokStudioLayoutError`
  nomeando o campo e o endpoint. Nada de zeros silenciosos.

### `PatchrightTikTokStudioProxy(user_data_dir, headless, timeouts)` — `src/proxies/tiktok_studio_proxy.py`

- `patchright.async_api.async_playwright().chromium.launch_persistent_context(
  user_data_dir, channel="chrome", headless=..., args e user agent do publisher)`.
  **Sem** o script do `playwright-stealth`: sob patchright ele fez toda navegação
  falhar com `ERR_NAME_NOT_RESOLVED` (research §2).
- Registra `page.on("response")` e guarda os corpos de `ITEM_LIST_PATH`
  (`/tiktok/creator/manage/item_list/v1/`) e `INSIGHT_PATH`
  (`/aweme/v2/data/insight/`), fixados pela sondagem. Navega para a lista de
  conteúdo, rola até um post não fixado mais velho que `since` ou `has_more`
  falso (três rolagens sem post novo → `TikTokStudioLayoutError`), e abre a
  analytics de cada vídeo pedido esperando a resposta com
  `video_finish_rate_realtime` daquele vídeo.
- Parser em funções puras (`_parse_video_list(body) -> list[TikTokVideoStats]`,
  `_parse_analytics(body) -> PerformanceMetrics`) testadas sobre
  `tests/fixtures/tiktok_studio_probe.json`.
- Fecha o contexto sempre (`finally`), com o mesmo teto de tempo do
  `_safe_stop` do publisher, para a sessão ser gravada em disco.
- Config: `TikTokStudioConfig(user_data_dir: str | None, headless: bool = False,
  lookback_days: int = 30, page_timeout_seconds: int = 60)`; `user_data_dir`
  `None` deriva de `tiktok_publisher_config.cookies_path` (`<stem>_userdata`).

### `scripts/tiktok_studio_probe.py` (M3)

Abre o mesmo contexto, navega às mesmas páginas, e grava em
`.storage/tiktok_studio_probe/<ts>/` um arquivo por resposta JSON (`NNN-<host>-<path>.json`
com URL, status e corpo) mais `page-*.png`. Não parseia nada. Receita
`just prod-tiktok-studio-probe` (xvfb-run) e `just sync-tiktok-studio-probe`.
É a ferramenta para regravar o fixture quando o Studio mudar.

## `PerformanceSource` — `src/capabilities/performance/contract.py` (M4)

```python
class PerformanceSource(Protocol):
    async def fetch(self, *, since: datetime) -> list[TikTokVideoStats]: ...
    async def metrics(self, video_id: str) -> PerformanceMetrics: ...
```

Implementação de produção: `StudioPerformanceSource(proxy: ITikTokStudioProxy)`,
um passa-adiante fino que existe para o fluxo não importar `proxies`. Fake:
`tests/fakes/performance.py::FakePerformanceSource(videos, metrics, fail=False)`.
Um export de arquivo do Studio, se vier um dia, é outra implementação deste
Protocol e não toca o fluxo (FR-020).

## Casamento — `src/capabilities/performance/matching.py` (M4)

```python
@dataclass(frozen=True)
class MatchResult:
    matched: dict[int, TikTokVideoStats]           # record_id -> vídeo
    unmatched: list[TikTokVideoStats]
    ambiguous: list[tuple[TikTokVideoStats, list[int]]]

def normalize_caption(text: str) -> str: ...
def match(records: list[PublishedRecord], videos: list[TikTokVideoStats],
          *, max_gap: timedelta = timedelta(hours=12)) -> MatchResult: ...
```

Regras, em ordem:

1. Registro com `tiktok_video_id` igual ao `video_id` → casado, sem olhar
   legenda.
2. `normalize_caption(video.description) == normalize_caption(record.title)`:
   remove hashtags finais (a mesma regra do publisher), dobra acentos e
   pontuação (`unidecode`; no servidor "café" voltou "cafe" e aspas curvas
   voltaram retas), colapsa espaços, `casefold`.
3. Vários candidatos por legenda → fica o(s) cujo último `scheduled_at` está a
   menos de `max_gap` do `video.created_at`; um → casado; zero ou mais de um →
   `ambiguous` com os ids candidatos.
4. Nenhum candidato → `unmatched`.
5. Um registro só casa com um vídeo; se dois vídeos casam o mesmo registro, os
   dois vão para `ambiguous` (republicação real; o operador decide).

Função pura, sem I/O, sem datas "agora".

## `StoryDiscovery.signals(url) -> RedditSnapshot` — `src/capabilities/discovery/contract.py` (M4)

Lê o post via `IRedditProxy.get_reddit_post` e devolve `RedditSnapshot(source=
"collection", taken_at=now, score, num_comments, upvote_ratio, available=True)`.
Post removido ou erro 404/403 do Reddit → `available=False` e números `None`;
qualquer outro erro estoura (rede fora é falha da coleta, não "post sumiu").
