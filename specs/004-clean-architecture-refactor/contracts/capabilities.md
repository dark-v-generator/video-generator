# Contratos das capacidades

Cada capacidade expõe um `typing.Protocol` em `contract.py`. Assinaturas em
Python para não haver ambiguidade; os nomes são definitivos, os tipos referem-se
a [data-model.md](../data-model.md). Nenhum contrato recebe `MainConfig`: cada
implementação recebe só a fatia de configuração que usa.

## Descoberta — `src/capabilities/discovery/contract.py` (M3)

```python
class StoryDiscovery(Protocol):
    def fetch(self, url: str) -> StoryOrigin: ...
    async def find_candidates(
        self, *, sort="top", time_filter="day", posts_per_sub=25, top_per_sub=5,
        subreddits: list[str] | None = None, exclude_urls: set[str] | None = None,
    ) -> list[StoryCandidate]: ...
    async def grade(
        self, candidates: list[StoryCandidate], language: Language
    ) -> list[EvaluatedStory]: ...
    async def find_best_stories(self, *, language: Language, subreddits=None,
                                exclude_urls=None, **kwargs) -> list[EvaluatedStory]: ...
```

- `find_candidates` nunca chama modelo; ranqueia com o score determinístico atual.
- `grade` é a avaliação por modelo com a mesma tolerância de hoje (falha em uma
  candidata vira nota 0 e veredito `Erro`, não derruba a lista).
- `find_best_stories` = `find_candidates` + `grade` + o corte atual (todas as
  `Excelente` se ≥ 10, senão as 10 melhores entre `Excelente`/`Boa`).
- Um subreddit que falha é registrado e pulado; todos falhando estoura
  `RuntimeError` com os detalhes (comportamento atual).
- Implementação: `RedditStoryDiscovery(reddit: IRedditProxy, llm: ILLMProxy,
  evaluation: EvaluationConfig)`.
- Garantia de isolamento: importar `src.capabilities.discovery` não importa
  `moviepy`, `whisper`, `torch` nem `playwright`.

## Escrita — `src/capabilities/writing/contract.py` (M2)

```python
class WriterError(Exception): ...
class WriterTransientError(WriterError): ...      # vale tentar de novo
class WriterContentBlockedError(WriterError): ... # não vale tentar de novo

class StoryWriter(Protocol):
    async def write(
        self, origin: StoryOrigin, *, language: Language,
        speech_gender: Literal["male", "female"] | None = None,
    ) -> Story: ...
```

- Devolve uma `Story` com uma ou mais partes. O escritor de produção
  (`ModelStoryWriter(llm: ILLMProxy)`) devolve sempre uma parte, título e
  gênero do modelo, `resolved_gender` pela regra do data-model, `summary` vazio
  (o fluxo preenche com o resumo da avaliação).
- `StaticStoryWriter(stories: dict[str, Story])` devolve a história registrada
  para `origin.url` e estoura `WriterError` para uma origem desconhecida. Sem
  chamada a modelo.
- Classificação de erro no `ModelStoryWriter`: rate limit do cliente, `429`,
  `rate limit`, `too many requests`, `timeout`, `502`, `503` → transitório;
  `safety filter`, `content filter`, `nsfw`, `blocked`, `content policy` →
  bloqueado; o resto → `WriterError` com a mensagem original.

## Prompts — `src/prompts/loader.py` (M2)

```python
def render(template_name: str, **variables) -> str
def validate_all() -> None   # compila cada *.jinja2; estoura TemplateSyntaxError nomeando o arquivo
def load_examples(name: str) -> list  # examples/<name>.yaml, [] se não existir
```

Templates: `story.jinja2`, `evaluate_story.jinja2`, `generate_hashtags.jinja2`,
`enhance_transcription.jinja2`. Texto inalterado.

## Footage — `src/capabilities/footage/contract.py` (M4)

```python
@dataclass
class Footage:
    clip: VideoClip            # src/entities/editor/video_clip.py, já com anti-fingerprint

class FootageShortfallError(Exception):
    needed: float; got: float

class FootageSource(Protocol):
    async def compile(self, *, min_duration: float, low_quality: bool = False) -> Footage: ...
```

- `YouTubeFootageSource(youtube: IYouTubeProxy, video: VideoConfig)`: listagem
  por estratégia (`random`/`all`), pool, embaralhamento, download com cache,
  parada no 429 completando do cache, anti-fingerprint por clipe; estoura
  `FootageShortfallError` quando o pool acaba antes da duração (hoje uma
  `Exception` genérica com o mesmo sentido) e relança o erro de throttle quando
  nem o cache cobre (comportamento atual).
- `LocalFolderFootageSource(directory: str, video: VideoConfig)`: `.mp4` do
  diretório em ordem aleatória, concatenados até `min_duration`, com o mesmo
  anti-fingerprint; `FootageShortfallError` com o déficit.

## Renderização — `src/capabilities/rendering/contract.py` (M5)

```python
class Renderer(Protocol):
    name: str
    async def render(self, story: Story, *, low_quality: bool = False) -> list[RenderedPart]: ...

def select_renderer(name: str, renderers: dict[str, Renderer]) -> Renderer
    # KeyError com a lista de nomes disponíveis
```

- `NarrationOverFootageRenderer` (`name = "narration-over-footage"`), construído
  com `SpeechService`, `CaptionsService`, `CoverService`, `FootageSource`,
  `VideoComposer` (o atual `VideoService.generate_video`), `TextCensor`,
  `VideoConfig`. Por parte, na ordem: fala (`resolved_gender`, `rate=1.0`,
  idioma) → legendas com correção pelo modelo usando o texto da parte → início
  do CTA (`_compute_satisfying_cta_start`, inalterado) → censura das legendas →
  capa com `story.cover_title_for(part)` censurado, comunidade, autor e imagem da
  origem → footage com `min_duration = duração da fala` → composição → mp4 em
  bytes (fps e ffmpeg da config).
- Uma parte que falha estoura; o renderizador não publica nem grava nada. O
  fluxo decide o que fazer (tudo ou nada).

## Publicação (M6)

O contrato é o `ITikTokPublisherProxy` existente (`publish_video(video_path,
description, hashtags, schedule_at) -> str`). Nenhuma mudança no proxy.

```python
class HashtagSuggester:   # src/capabilities/publishing/hashtags.py
    def __init__(self, llm: ILLMProxy, defaults: list[str], language: Language): ...
    async def suggest(self, *, title: str, summary: str) -> list[str]
        # defaults + generate_hashtags, normalizados (normalize_hashtags atual)
    def normalize(self, raw: list[str]) -> list[str]
        # defaults + raw, para hashtags já escolhidas (Story.hashtags)
```

A aritmética de slots (`next_publish_slot`, `compute_publish_slots`) fica em
`src/flows/publish_slots.py`, fora do publisher, com as assinaturas atuais.
