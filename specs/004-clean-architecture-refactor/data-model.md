# Data Model: Capacidades isoladas e fluxos de negócio finos

**Feature**: 004-clean-architecture-refactor | **Date**: 2026-09-25

Entidades sem I/O, em `src/entities/`. Dataclasses simples, exceto onde a
serialização exige pydantic (configuração e `RedditPost`, que já é pydantic).

## StoryOrigin (`src/entities/story.py`, M2)

O texto de origem de uma história e a atribuição que a capa mostra. Hoje é um
post do Reddit; a entidade não sabe disso.

| Campo | Tipo | Origem hoje |
|-------|------|-------------|
| `url` | `str` | `RedditPost.url` (permalink); identifica a história no publish log e nas exclusões |
| `title` | `str` | `RedditPost.title` |
| `content` | `str` | `RedditPost.content` |
| `community` | `str` | `RedditPost.community` (`r/...`), vai para a capa |
| `author` | `str` | `RedditPost.author`, vai para a capa |
| `community_image_url` | `str` | `RedditPost.community_url_photo`, vai para a capa |

`StoryOrigin.from_post(post: RedditPost)` é o único ponto que conhece `RedditPost`.
`original_markdown` (propriedade): `# {title}\n\n{content}\n`, o que hoje vira
`original_post.md`.

## StoryPart (`src/entities/story.py`, M2)

| Campo | Tipo | Regra |
|-------|------|-------|
| `index` | `int` | 1-based, contíguo |
| `text` | `str` | narração da parte, usada verbatim; não vazia |

## Story (`src/entities/story.py`, M2)

| Campo | Tipo | Regra |
|-------|------|-------|
| `title` | `str` | título da capa, usado verbatim (censurado só na renderização) |
| `parts` | `list[StoryPart]` | 1 ou mais; índices 1..N |
| `narrator_gender` | `"male" \| "female" \| "unknown"` | o que o escritor identificou |
| `resolved_gender` | `"male" \| "female"` | voz efetiva: pedido do chamador, senão `narrator_gender` se conhecido, senão `male` (regra atual de `prepare_satisfying_story`) |
| `language` | `Language` | idioma da narração |
| `summary` | `str` | resumo curto; hoje vem da avaliação (`resumo[:400]`), pode ser vazio |
| `origin` | `StoryOrigin` | |
| `hashtags` | `list[str] \| None` | quando presente, a publicação não pede hashtags ao modelo (hoje sempre `None` na rodada diária) |

Métodos:
- `is_multipart` → `len(parts) > 1`.
- `cover_title_for(part)` → `title` quando há uma parte; `f"{title}{part_label(language, part.index)}"` quando há mais. `part_label("pt-br", n)` = `" - Parte {n}"`; outros idiomas usam o mesmo formato com a palavra localizada (`" - Part {n}"` em inglês). Só `pt-br` é usado hoje.
- `story_markdown` (propriedade): o `story.md` de hoje: `# {title}`, linha do gênero, e cada parte separada por um cabeçalho quando há mais de uma.

Validação: `parts` não vazia, textos não vazios, índices contíguos. Estoura
`ValueError` na construção.

## RenderedPart (`src/entities/rendered.py`, M5)

Os artefatos de uma parte renderizada. O que `SingleVideoResult` é hoje, por parte.

| Campo | Tipo |
|-------|------|
| `part` | `StoryPart` |
| `cover_title` | `str` (já com o sufixo, já censurado) |
| `video` | `bytes` |
| `audio` | `bytes` |
| `captions_json` | `str` (lista de `{word, start, end}` censurada) |
| `cover_png` | `bytes \| None` |

## GeneratedVideo (`src/entities/generated_video.py`, M6)

O manifest de um vídeo pronto para publicar. Movido do bot sem mudar campos.

| Campo | Tipo | Manifest (`story_NN.json`) |
|-------|------|----------------------------|
| `video_path` | `str` | `video_path` |
| `title` | `str` | `title` (é a descrição do post no TikTok) |
| `summary` | `str` | `summary` |
| `post_url` | `str` | `post_url` |
| `source` | `str` | `source`, sempre `"auto"` agora; ausente em manifests antigos → `"auto"` |
| `part` | `int \| None` | `part`, só gravado quando não é `None`; ausente → `None` |

Nome do arquivo: `story_{NN:02d}.mp4` para a parte única ou parte 1;
`story_{NN:02d}_p{k}.mp4` para `k ≥ 2` (hoje `_p2`). Manifest com o mesmo
basename e extensão `.json`.

## PublishLogEntry (`src/storage/contract.py`, M6)

Uma linha de `.storage/tiktok_publish_log.csv`. Colunas, nesta ordem:
`created_at`, `status`, `scheduled_at`, `video_path`, `title`, `post_url`,
`hashtags`, `publish_result`, `error`. `status ∈ {scheduled, failed}`;
`scheduled_at` em ISO com minutos; `hashtags` como `#a #b`. Inalterado.

## Candidatas e avaliação (inalterados)

`StoryCandidate` e `EvaluatedStory` (`src/entities/story_candidate.py`) ficam
como estão; `RedditPost` idem. A descoberta continua devolvendo `EvaluatedStory`
com `resumo`, `nota_geral`, `veredito`.

## Configuração

### Mantido (lido do mesmo lugar)

- `bots.satisfying_bot.{allowed_user_ids, low_quality, daily_hour_utc,
  daily_minute_utc, daily_auto_publish_count, publish_slots_local,
  publish_min_lead_minutes, publish_hashtags}`.
- `language`, `evaluation.*`, `proxies.{reddit_config, llm_config,
  history_adaptation_llm_config, speech_config, transcription_config,
  youtube_config, cover_config, tiktok_publisher_config}`.
- `services.{video_config, captions_config, censorship_config}`.

### Novo (com padrão que reproduz hoje)

| Chave | Tipo | Padrão | Milestone |
|-------|------|--------|-----------|
| `services.video_config.footage_source` | `"youtube" \| "local"` | `"youtube"` | M4 |
| `services.video_config.local_footage_dir` | `str \| None` | `None` (obrigatório com `local`) | M4 |
| `services.video_config.rendering_strategy` | `"narration-over-footage"` | `"narration-over-footage"` | M5 |

### Ignorado (features removidas; pydantic descarta chaves desconhecidas)

`proxies.image_generation_config`, `proxies.portrait_generation_config`,
`bots.image_story_bot`, `bots.satisfying_bot.prepared_stories`,
`services.video_config.draw_transition_duration`. Os arquivos `config*.yaml` do
repositório têm esses blocos apagados no M1; um `config.yaml` local antigo
continua carregando.

### DailyRunConfig (`src/entities/configs/flows.py`, M6)

Montado no container a partir de `bots.satisfying_bot` e `language`; o fluxo
não lê `MainConfig`.

| Campo | Fonte |
|-------|-------|
| `count` | `daily_auto_publish_count` |
| `publish_slots_local` | idem |
| `publish_min_lead_minutes` | idem |
| `publish_hashtags` | idem |
| `low_quality` | idem |
| `language` | `language` |
| `story_retry_max`, `story_retry_base_delay` | constantes atuais (3, 5 s) |

## Transições de estado da rodada (inalteradas)

Por história, na ordem das candidatas: `roteiro` (retry até 3× em erro
transitório; bloqueada → pula; outro erro → pula) → `renderização` (falha em
qualquer parte → pula, nada publicado) → `publicação` (parte k no slot seguinte
ao da parte k-1; falha → linha `failed` no log, pula). A rodada termina quando
`count` histórias foram publicadas (ou geradas, no generate-only) ou as
candidatas acabam.
