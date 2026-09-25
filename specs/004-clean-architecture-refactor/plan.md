# Implementation Plan: Capacidades isoladas e fluxos de negócio finos

**Branch**: `004-clean-architecture-refactor` (a criar a partir de `main`) | **Date**: 2026-09-25 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/004-clean-architecture-refactor/spec.md`

## Summary

Reorganizar a aplicação em cinco **capacidades** independentes (descoberta, escrita,
footage, renderização, publicação), um **modelo de história com N partes**, uma
**fronteira de armazenamento** e um único **fluxo de negócio**, a rodada diária, que
apenas combina essas peças. O bot do Telegram e o script de linha de comando viram
adaptadores que chamam o fluxo e recebem progresso.

Tudo o que não é a rodada diária sai antes da extração: a preparação local de
histórias com sua fila no servidor, o formato em duas partes, o pipeline de image
story, o bot interativo e o ponto de entrada web morto. Isso deixa
`RedditVideoService` (1096 linhas) e `bots/satisfying_bot.py` (1577 linhas) pequenos
o bastante para serem desmontados em uma capacidade por PR, com a rodada diária
implantável a cada passo.

A equivalência de comportamento é garantida por um **teste golden** gravado no
primeiro milestone, a partir do código antigo já sem as features removidas: a mesma
sequência de candidatas e as mesmas respostas falsas de modelo, fala, transcrição,
capa, footage e publisher têm que produzir os mesmos manifests, as mesmas linhas do
publish log e as mesmas mensagens de progresso no último milestone.

## Technical Context

**Language/Version**: Python 3.12 (venv atual), `requires-python >= 3.11`

**Primary Dependencies**: pydantic (entidades e configuração), dependency-injector
(`src/core/container.py`), jinja2 (prompts), litellm via `PromptLLMProxy` (escrita,
avaliação, hashtags, correção de legendas), edge-tts / elevenlabs (fala),
openai-whisper local (transcrição), moviepy (composição de vídeo, via
`src/entities/editor`), pytubefix + cache local (footage), playwright (capa),
browser-use + patchright (publicação no TikTok), python-telegram-bot (adaptador do
bot). Nenhuma dependência nova.

**Storage**: sistema de arquivos, como hoje: `output/daily/story_NN.mp4` e
`story_NN.json` (manifests), `.storage/tiktok_publish_log.csv` (histórico de
publicação), cache de backgrounds em `~/.cache/video-generator/backgrounds`. A
fronteira de armazenamento é uma interface com a implementação em arquivos
reproduzindo exatamente esses caminhos e formatos; uma implementação em memória
vive nos testes.

**Testing**: pytest (`tests/`, `asyncio_mode = auto`), sem rede. Linha de base ao
início: ~360 testes, com uma falha pré-existente em
`tests/test_translation_pipeline.py` (script manual, removido neste plano).
Novo: `tests/fakes/` (proxies falsos, footage local, store em memória) e o golden
`tests/flows/test_daily_run_golden.py`.

**Target Platform**: Linux (servidor: `systemd` roda `python -m bots.satisfying_bot`
com `config.prod.yaml`) e macOS (laptop: `scripts/daily_auto_publish.py` e testes).

**Project Type**: projeto único, Clean Architecture em módulos.

**Performance Goals**: SC-007: importar a descoberta em menos de 2 s e sem carregar
moviepy/whisper; SC-002: suíte inteira do fluxo sem rede e sem modelo.

**Constraints**: SC-001 (equivalência da rodada diária, verificada pelo golden);
SC-009 (fluxo diário em um módulo de até 300 linhas sem Telegram, terminal ou
layout de arquivos); FR-018 (configs atuais continuam válidas; chaves das features
removidas são ignoradas, o que o pydantic já faz por padrão em `BaseYAMLModel`);
FR-019 (manifests antigos continuam carregando no publish-only).

**Scale/Scope**: 1 operador, 3 vídeos/dia. Remoção de ~6 mil linhas (bots, scripts,
proxies de imagem, pacotes, fila, testes das features removidas) e realocação de
~3 mil. 7 PRs.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Avaliação | Resultado |
|-----------|-----------|-----------|
| I. Fail Fast e Simplicidade | A refatoração remove ramos em vez de acrescentar: some a distinção "uma parte / duas partes" no bot, some o item de trabalho com dois estados (`prepared` / `story`), some a fila com seus estados de erro. Os pontos novos falham cedo: prompt inválido estoura ao construir o container (`validate_all`), estratégia de renderização desconhecida estoura na seleção, footage insuficiente estoura com o déficit em segundos. A política de retry/skip do roteiro existente é mantida no fluxo, sem novos casos raros. | PASS |
| II. Arquitetura Limpa em Módulos | É o objeto da feature. Entidades (`Story`, `RenderedPart`, `GeneratedVideo`) sem I/O no centro; capacidades com um contrato (`Protocol`) cada e implementações que dependem só de proxies; proxies inalterados nas bordas; o fluxo depende apenas de contratos e recebe tudo por injeção; os adaptadores (Telegram, CLI) só traduzem comandos e progresso. Dependências apontam de fora para dentro: `flows` → `capabilities` → `proxies`/`entities`; `bots`/`scripts` → `flows`. Um teste de importação garante que `capabilities.discovery` não carrega o stack de vídeo. | PASS |
| III. Prompts Baseados em Racional | Os prompts que ficam (`story`, `evaluate_story`, `generate_hashtags`, `enhance_transcription`) já são prosa com racional (PR #5895aeb) e não mudam de texto; só mudam de lugar (`src/prompts/`) e ganham validação no boot. Nenhum prompt novo. | PASS |
| Idioma | Plano, research, data-model, contracts e quickstart em português; código, comentários, commits e nomes de arquivos em inglês. `spec.md` em inglês acompanhando o pedido do usuário (mesmo desvio documentado nas features 002 e 003). | PASS (desvio documentado) |

**Re-check pós-design (Phase 1)**: o desenho final não introduz camada que conheça
camada externa. A única concessão é o `ModelStoryWriter` conhecer a classe de erro
de rate limit do cliente de modelo para classificá-la como transitória; isso fica
na capacidade de escrita, não no fluxo, e é o que retira o `import litellm` do bot.
Registrado em Complexity Tracking. PASS.

## Delivery Plan

7 milestones, 1 PR cada. A ordem é remoção primeiro (deixa menos código para mover),
depois extração de baixo para cima (modelo e escrita, descoberta, footage,
renderização), depois o fluxo com o armazenamento e os adaptadores, e por fim
documentação e limpeza. A rodada diária continua implantável ao fim de cada PR: até
o M5 ela ainda roda pelo código antigo do bot, que vai sendo apontado para as
capacidades novas uma de cada vez; no M6 o bot passa a chamar o fluxo.

### M1 — Remover o que não é a rodada diária e gravar o golden (US8) — PR 1

**Remoção** (FR-020 a FR-023):
- Preparação local e fila: `scripts/prepare_story.py`, `.claude/skills/prepare-story/`,
  `src/entities/prepared_story.py`, `src/services/prepared_story_queue.py`,
  `src/services/prepared_story_validation.py`, `src/proxies/prompts/render.py`,
  `docs/prepared-stories.md`, receitas `story-*` do `Justfile`, `PreparedStoriesConfig`
  e o campo `prepared_stories` em `src/entities/configs/bots.py`, o provider
  `prepared_story_queue` do container, os blocos comentados em `config*.yaml`; testes
  `test_prepare_story_cli.py`, `test_prepared_story_package.py`,
  `test_prepared_story_queue.py`, `test_render_story_prompt.py`,
  `test_render_two_part_prompt.py`.
- Duas partes: `src/proxies/prompts/two_part_story.jinja2`, `revise_story.jinja2`,
  `src/proxies/examples/two_part_story.yaml`, `scripts/reddit_two_part_history.py`,
  receitas `generate-reddit*`, os métodos `generate_two_part_story` e `revise_story`
  de `ILLMProxy` e dos três proxies (`prompt`, `dspy`, `mock`) com suas signatures;
  em `RedditVideoService`, `StoryScript`, `AudioPair`, `CaptionsPair`, `VideoPair`,
  `TwoPartVideoResult` e os métodos `generate_script`, `revise_script`,
  `generate_audio`, `generate_captions_pair`, `generate_cover_pair`,
  `compose_two_part_video`, `generate_two_part_history_video`; testes
  `test_two_part_story.py`, `services/test_hook_quality.py` (guarda os exemplos de
  duas partes), `services/test_content_boundaries.py` (cobre `_compute_content_boundaries`,
  usado só pelo image story).
- Image story e bot interativo: `bots/image_story_bot.py`, `bots/interactive_bot.py`,
  `scripts/image_story_video.py`, `scripts/test_image_story.py`,
  `src/entities/image_story.py`, `generate_characters` e `generate_image_story` de
  `ILLMProxy` e proxies, prompts `generate_characters.jinja2` e
  `generate_image_story.jinja2`; em `RedditVideoService`, `CharacterSheet`,
  `ImageStoryPair`, `ImageStoryVideoResult`, `generate_characters`,
  `generate_image_stories`, `compose_image_story_video`, `generate_image_story_video`,
  `_compute_content_boundaries`, `_shift_images_back`, `_strip_introduction`,
  `_extract_style_context`, `_generate_images_for_story`, `_render_image_story_to_bytes`;
  em `VideoService`, `generate_image_story_video`, `_build_image_segments`,
  `_create_ken_burns_clip`, `_create_brush_mask_clip`, `_generate_brush_reveal_map`,
  `_blur_image_bytes` e `draw_transition_duration` do `VideoConfig`; os proxies de
  geração de imagem e vídeo (`leonardo_proxy`, `leonardo_v2_proxy`, `midjourney_proxy`,
  `local_sdxl_proxy`, `runpod_comfyui_proxy`, `mock_image_proxy`, `comfyui_video_proxy`),
  `IImageGeneratorProxy`, `IVideoGeneratorProxy`, suas configs
  (`configs/proxies/image_generation.py`, `video_generation.py`), as fábricas
  `ImageGeneratorFactory` e `VideoGeneratorFactory`, os campos
  `image_generation_config` e `portrait_generation_config` de `ProxiesConfig`, os
  segredos `leonardo_api_key`, `runpod_api_key`, `legnext_api_key`,
  `telegram_image_story_bot_token`, o campo `bots.image_story_bot`, e
  `send_image_bytes` de `bots/base.py`.
- Mortos: `main.py` (aponta para `src.main_fastapi`, inexistente), `src/entities/reddit.py`,
  `src/entities/reddit_history.py`, `src/entities/history.py`,
  `tests/test_translation_pipeline.py` e `tests/test_transcription_enhance.py`
  (scripts manuais que chamam rede; o segundo usa `DSPyLLMConfig` como padrão),
  `tests/script_youtube_download.py` (idem).
- No bot: `/prepared`, `_WorkItem.prepared/part2/queued/story_title`,
  `_collect_candidates` volta a ser "descoberta com `exclude_urls` = publish log",
  `_generate_video_for_story` produz um vídeo, `_publish_item` publica um vídeo,
  `_outcome`, `_mark_done`, `_mark_failed`, `_queue`. O manifest mantém
  `source: "auto"` (FR-019, equivalência) e `GeneratedVideo.part` some.
- `pyproject.toml`: nenhuma dependência removida neste PR; a limpeza de dependências
  órfãs (`coqui-tts`, `azure-cognitiveservices-speech`, `fastapi`, `uvicorn`,
  `ollama`, `anthropic`) fica para o M7, depois que o grep de uso confirmar.

**Golden**: `tests/fakes/` com `FakeRedditProxy`, `FakeLLMProxy` (roteiro, avaliação,
hashtags e correção de legendas determinísticos), `FakeSpeechProxy`,
`FakeTranscriptionProxy`, `FakeCoverProxy`, `FakePublisher`, e um `FakeVideoService`
que devolve bytes fixos; `tests/flows/test_daily_run_golden.py` roda os três modos
pelo bot antigo (`run_daily_auto_publish`, `run_daily_generate`, `run_daily_publish`)
com uma falha de roteiro transitória, uma bloqueada por filtro e uma falha de
publicação, e grava `tests/fixtures/daily_run_golden.json` com: sequência de
mensagens, manifests (dict), linhas do publish log (sem `created_at`) e chamadas ao
publisher (caminho, descrição, hashtags, slot). O teste compara com o arquivo; o
arquivo só é regravado com `--update-golden`.

**Gate de verificação M1**:
- Testes: suíte verde (`uv run pytest -q`); golden gravado e passando; os testes que
  ficaram de `test_daily_prepared_flow.py` (renomeado `tests/flows/test_daily_run.py`:
  `TestGenerateOnly`, `TestScheduledPostUrls`, `TestLoadGeneratedVideos`,
  `TestPublishFromDirectory`) e `test_publish_slots.py` passam.
- SC-011: `grep -rEi "prepared|two.?part|image.?story|interactive_bot|main_fastapi"
  --include=*.py --include=*.md --include=*.yaml --include=Justfile .` só encontra
  ocorrências em `specs/`.
- Manual: `uv run python -m bots.satisfying_bot` sobe com `config.dev.yaml`;
  `just daily-generate 1` com `config.dev.yaml` (mock LLM) produz `story_01.mp4`
  e `story_01.json` com `source: auto`.

### M2 — Modelo de história e capacidade de escrita (US2, modelo de US6) — PR 2

- `src/entities/story.py`: `StoryOrigin`, `StoryPart`, `Story` (ver data-model.md).
  `Story.cover_title_for(part)` aplica ` - Parte N` só quando há mais de uma parte.
- `src/prompts/`: templates e `examples/` movidos de `src/proxies/prompts` e
  `src/proxies/examples`; `loader.py` com `render(name, **vars)` e `validate_all()`
  (compila todos os templates; erro nomeia o arquivo). Os três proxies de LLM passam a
  usar o loader. O container chama `validate_all()` na construção de `llm_proxy`.
- `src/capabilities/writing/`: `contract.py` (`StoryWriter` Protocol,
  `WriterError`, `WriterTransientError`, `WriterContentBlockedError`),
  `model_writer.py` (`ModelStoryWriter(llm)`: `generate_story` → `Story` de uma parte,
  com a resolução de gênero e a classificação de erro que hoje estão no serviço e no
  bot), `static_writer.py` (`StaticStoryWriter(stories)`: devolve a história já escrita
  para uma origem, para testes e para o futuro fluxo local).
- `ILLMProxy` fica com `generate_story`, `evaluate_story`, `generate_hashtags`,
  `enhance_transcription`.
- Bot: `_prepare_story_with_retries` chama `container.story_writer()` em vez de
  `service.prepare_satisfying_story`; o serviço recebe `Story` em
  `generate_satisfying_video_from_story` (adaptador mínimo `PreparedStory` → `Story`
  some junto com `PreparedStory`).

**Gate de verificação M2**:
- Testes: `ModelStoryWriter` com LLM falso devolve `Story` de uma parte com título,
  gênero resolvido e origem; classificação de erro (429 → transitório; "content
  filter" → bloqueado; outro → `WriterError`); `StaticStoryWriter` sem chamada ao LLM;
  `validate_all()` estoura nomeando um template com sintaxe quebrada; `Story` com 3
  partes produz `cover_title_for` com ` - Parte 3` e com 1 parte sem sufixo; golden
  continua passando.
- Manual: editar `src/prompts/story.jinja2` e ver o texto novo no log de
  `PromptLLMProxy` com `config.dev.yaml`.

### M3 — Capacidade de descoberta (US4) — PR 3

- `src/capabilities/discovery/`: `contract.py` (`StoryDiscovery` Protocol:
  `fetch(url) -> StoryOrigin`, `find_candidates(...)`, `grade(candidates, language)`,
  `find_best_stories(...)` = composição) e `reddit_discovery.py`
  (`RedditStoryDiscovery(reddit, llm, evaluation_config)`, o conteúdo de
  `story_finder_service.py` mais o `scrape_post` do serviço).
- Scripts de diagnóstico `find_best_stories.py`, `evaluate_story.py`, `list_posts.py`
  passam a usar `container.story_discovery()`.
- Bot: `_discover_stories` usa a capacidade; a re-leitura do post por URL antes de
  escrever (hoje em `prepare_satisfying_story`) vira `discovery.fetch(url)` no bot.
- `tests/capabilities/test_import_isolation.py`: importar `src.capabilities.discovery`
  num subprocesso não carrega `moviepy`, `whisper` nem `torch` (SC-007).

**Gate de verificação M3**:
- Testes: os de `tests/services/test_story_finder_service.py` movidos para
  `tests/capabilities/test_discovery.py` sem mudança de asserção; `grade` não é chamado
  por `find_candidates`; `exclude_urls` respeitado; falha em um subreddit não derruba os
  outros; isolamento de import; golden passando.
- Manual: `uv run python scripts/find_best_stories.py` lista candidatas com
  `config.dev.yaml`; `time python -c "import src.capabilities.discovery"` < 2 s.

### M4 — Capacidade de footage (US5) — PR 4

- `src/capabilities/footage/`: `contract.py` (`Footage`, `FootageSource` Protocol:
  `compile(min_duration, low_quality) -> Footage`, `FootageShortfallError`),
  `youtube.py` (`YouTubeFootageSource(youtube_proxy, video_config)`: o conteúdo de
  `create_youtube_video_compilation`, `_finish_without_network`, listagem e
  anti-fingerprint), `local_folder.py` (`LocalFolderFootageSource(dir, video_config)`:
  concatena os `.mp4` do diretório em ordem aleatória até a duração, com o mesmo
  anti-fingerprint).
- `VideoConfig` ganha `footage_source: Literal["youtube", "local"] = "youtube"` e
  `local_footage_dir: Optional[str]`; os campos `youtube_*` ficam onde estão (FR-018).
  Container: `footage_source` escolhido por config; `local` sem diretório estoura na
  construção.
- `VideoService` fica só com `generate_video` (composição); `_render_video_to_bytes`
  do serviço passa a receber `Footage` de `footage_source.compile(...)`.

**Gate de verificação M4**:
- Testes: `tests/services/test_video_service.py` e `test_compilation_rate_limit.py`
  movidos para `tests/capabilities/test_footage_youtube.py` sem mudança de asserção;
  `LocalFolderFootageSource` cobre a duração com clipes falsos e estoura
  `FootageShortfallError` com o déficit quando não cobre; `footage_source: local` sem
  diretório falha na construção do container; golden passando.
- Manual: `footage_source: local` com dois `.mp4` numa pasta e `just daily-generate 1`
  com `config.dev.yaml` produz o vídeo sem tocar no YouTube (log sem `pytubefix`).

### M5 — Capacidade de renderização (US1, renderização de US6) — PR 5

- `src/entities/rendered.py`: `RenderedPart` (parte, vídeo, áudio, legendas JSON,
  capa PNG, título da capa).
- `src/capabilities/rendering/`: `contract.py` (`Renderer` Protocol:
  `render(story, low_quality) -> list[RenderedPart]`), `narration_over_footage.py`
  (`NarrationOverFootageRenderer(speech, captions, cover, footage, compose, censor,
  video_config)`: por parte, fala → legendas corrigidas → censura → capa com
  `cover_title_for` → footage → composição → bytes; é o corpo atual de
  `generate_satisfying_video_from_story` + `_render_video_to_bytes` +
  `_compute_satisfying_cta_start`), `speech.py`, `captions.py`, `cover.py`,
  `compose.py` (movidos de `src/services/`), `censor.py` (`text_censor.py`),
  `registry.py` (`select_renderer(name, renderers)` estoura nomeando a estratégia
  desconhecida).
- `VideoConfig.rendering_strategy: Literal["narration-over-footage"]` com esse
  padrão. Container: `renderers` (dict) e `renderer` (selecionado).
- `RedditVideoService` e `src/services/` são apagados; o bot chama
  `renderer.render(story)`.

**Gate de verificação M5**:
- Testes: render de história de 1 parte com fakes (sem rede) devolve 1 `RenderedPart`
  com vídeo, áudio, legendas e capa, título da capa sem sufixo, `cta_start` calculado
  como hoje (teste de `_compute_satisfying_cta_start` migrado); história de 3 partes
  devolve 3 partes com ` - Parte N` na capa (SC-004, metade da renderização); a
  censura de legendas e de título é aplicada; `select_renderer("animation")` estoura
  nomeando a estratégia; `tests/services/test_video_clip_duration.py`,
  `test_cover_layout.py`, `test_text_censor.py` movidos sob `tests/capabilities/`;
  golden passando.
- Manual: `just daily-generate 1` com `config.dev.yaml` produz vídeo visualmente igual
  ao do M1 (mesma capa, legendas, CTA); SC-008: um script de 40 linhas em
  `scripts/render_story.py` (novo, mantido como exemplo) renderiza um JSON de história
  escrito à mão sobre uma pasta local só com `container.renderer()`.

### M6 — Fluxo diário, armazenamento e adaptadores (US3, US7, agendamento de US6) — PR 6

- `src/entities/generated_video.py`: `GeneratedVideo` (manifest) movido do bot, com
  `part: Optional[int]` para o modelo de N partes.
- `src/storage/`: `contract.py` (`RunStore` Protocol: `save_manifest`,
  `load_manifests(dir)`, `append_publish_log(entry)`, `scheduled_post_urls()`) e
  `files.py` (`FileRunStore(publish_log_path)`: o código atual de `_save_manifest`,
  `load_generated_videos`, `_append_publish_log`, `_scheduled_post_urls`, mesmos
  caminhos, mesmos campos, mesma ordem de colunas). `tests/fakes/memory_store.py`.
- `src/flows/publish_slots.py`: `next_publish_slot`, `compute_publish_slots` movidos
  do bot. `src/flows/progress.py`: `Progress = Callable[[str], Awaitable[None]]` e
  `RunLock`.
- `src/capabilities/publishing/hashtags.py`: `HashtagSuggester(llm, defaults)` =
  `generate_hashtags` + `normalize_hashtags` + hashtags configuradas.
  `ITikTokPublisherProxy` continua sendo o contrato de publicação; a construção do
  publisher sai do bot para o container (`tiktok_publisher`).
- `src/flows/daily_run.py`: `DailyRun(discovery, writer, renderer, publisher,
  hashtags, store, config: DailyRunConfig, progress, now)` com `generate(count,
  output_dir)`, `publish(videos)` e `run(count, output_dir)`. Contém as decisões de
  negócio (meta do dia, retry/skip do roteiro, próximo slot, N partes tudo ou nada,
  parte N+1 no slot seguinte) e nada de Telegram, terminal ou caminhos. Mensagens de
  progresso idênticas às de hoje (golden). `DailyRunConfig` é montado a partir de
  `bots.satisfying_bot` + `language` (FR-018).
- `bots/satisfying_bot.py` (adaptador, ~250 linhas): `/start`, URL → vídeo sob demanda
  (writer + renderer + `send_video_bytes`, com a fila de jobs), `/autopost` e o
  agendamento diário chamando `container.daily_run(progress)` sob `RunLock`.
  `/find` com botões some (ver research.md, decisão 7).
- `scripts/daily_auto_publish.py` (adaptador): três modos chamando `DailyRun` com
  progresso em stdout.

**Gate de verificação M6**:
- Testes: o golden passa com o fluxo novo, sem alteração do fixture (SC-001);
  `DailyRun` com store em memória produz os mesmos manifests e linhas (SC-006); os
  três modos rodam sem rede (SC-002); bot e CLI chamam o mesmo `DailyRun` (teste de
  adaptador com `DailyRun` falso); história de 3 partes no fluxo → 3 vídeos em 3 slots
  consecutivos, 3 linhas no log, 1 na meta, falha em qualquer parte → nenhum publicado
  (SC-004, metade do agendamento); manifests antigos sem `source` e sem `part` carregam
  (FR-019); `wc -l src/flows/daily_run.py` ≤ 300 e `grep -E "telegram|argparse|os.path"`
  vazio no arquivo (SC-009).
- Manual: `just daily-generate 1` e `just daily-publish-only output/daily` com
  `config.dev.yaml`; no servidor, `just deploy` e `just prod-daily-generate 1`.

### M7 — Documentação, dependências e limpeza final — PR 7

- `docs/architecture.md` reescrito (capacidades, fluxo, adaptadores, armazenamento,
  como registrar uma estratégia de renderização ou uma fonte de footage);
  `docs/configuration.md` (seções de image generation e prepared stories removidas;
  `footage_source`, `local_footage_dir`, `rendering_strategy` documentados);
  `docs/quickstart.md` (só a rodada diária); `README.md` (seções de image story, duas
  partes e preparação local removidas); `AGENTS.md`.
- `pyproject.toml`: remoção das dependências sem uso confirmado por grep.
- Verificação final de SC-003, SC-005, SC-007, SC-010, SC-011 registrada no plano
  (seção "Verificação pós-implementação").

**Gate de verificação M7**:
- `uv sync` e suíte verde depois da remoção de dependências; `black --check`; grep de
  SC-011 vazio fora de `specs/`; `docs/architecture.md` descreve cada diretório que
  existe e nenhum que não existe.

**Projeção**: 7 PRs.

## Project Structure

### Documentation (this feature)

```text
specs/004-clean-architecture-refactor/
├── plan.md              # Este arquivo
├── research.md          # Phase 0: decisões de desenho e alternativas
├── data-model.md        # Phase 1: Story, StoryPart, StoryOrigin, RenderedPart, GeneratedVideo, config
├── quickstart.md        # Phase 1: guia de validação por milestone
├── contracts/
│   ├── capabilities.md  # Contratos de descoberta, escrita, footage, renderização, publicação
│   ├── flow.md          # DailyRun: entradas, modos, decisões, mensagens de progresso
│   ├── storage.md       # RunStore: manifests e publish log (formatos preservados)
│   └── config.md        # Chaves de configuração novas, mantidas e ignoradas
└── tasks.md             # Phase 2 (/speckit-tasks — não criado por /speckit-plan)
```

### Source Code (repository root)

```text
src/
├── core/
│   ├── container.py            # M2..M6: providers das capacidades, renderers, store, daily_run (Factory)
│   ├── secrets.py              # M1: sem chaves de imagem e do bot de image story
│   └── logging_config.py
├── entities/
│   ├── story.py                # M2: NOVO — StoryOrigin, StoryPart, Story
│   ├── rendered.py             # M5: NOVO — RenderedPart
│   ├── generated_video.py      # M6: NOVO — GeneratedVideo (manifest), movido do bot
│   ├── reddit_post.py, story_candidate.py, captions.py, cover.py, language.py,
│   │   speech_voice.py, transcription.py     # INALTERADOS
│   ├── configs/
│   │   ├── proxies/            # M1: sem image_generation.py e video_generation.py
│   │   ├── services/video.py   # M4: footage_source, local_footage_dir; M5: rendering_strategy
│   │   ├── bots.py             # M1: sem PreparedStoriesConfig e image_story_bot
│   │   └── flows.py            # M6: NOVO — DailyRunConfig (montado de bots.satisfying_bot)
│   └── editor/                 # INALTERADO (wrappers moviepy)
├── prompts/                    # M2: NOVO — story.jinja2, evaluate_story.jinja2, generate_hashtags.jinja2,
│   ├── examples/               #      enhance_transcription.jinja2, examples/transcription_enhancement.yaml
│   └── loader.py               #      render(name, **vars), validate_all()
├── proxies/                    # M1: sem proxies de imagem/vídeo; ILLMProxy enxuto (M1/M2)
│   ├── interfaces.py           # M1/M2: IRedditProxy, ITranscriptionProxy, ISpeechProxy, ILLMProxy (4 métodos),
│   │                           #        IYouTubeProxy, ICoverProxy, ITikTokPublisherProxy
│   ├── factories.py            # M1: sem ImageGeneratorFactory / VideoGeneratorFactory
│   └── ...                     # demais proxies INALTERADOS
├── capabilities/
│   ├── discovery/              # M3: contract.py, reddit_discovery.py
│   ├── writing/                # M2: contract.py, model_writer.py, static_writer.py
│   ├── footage/                # M4: contract.py, youtube.py, local_folder.py
│   ├── rendering/              # M5: contract.py, narration_over_footage.py, speech.py, captions.py,
│   │                           #     cover.py, compose.py, censor.py, registry.py
│   └── publishing/             # M6: hashtags.py (contrato de publicação = ITikTokPublisherProxy)
├── storage/                    # M6: contract.py (RunStore), files.py (FileRunStore)
└── flows/                      # M6: daily_run.py (≤ 300 linhas), publish_slots.py, progress.py

bots/
├── base.py                     # M1: sem send_image_bytes
└── satisfying_bot.py           # M1: sem fila/duas partes; M6: adaptador (~250 linhas)

scripts/
├── daily_auto_publish.py       # M6: adaptador CLI do DailyRun
├── render_story.py             # M5: NOVO — exemplo SC-008 (história JSON + pasta local → vídeo)
├── find_best_stories.py, evaluate_story.py, list_posts.py   # M3: usam a descoberta
├── publish_tiktok.py, tiktok_repl.py, tiktok_caption_snippet.py,
│   server-tiktok-vnc-bootstrap.sh                            # INALTERADOS (tooling do TikTok)
└── generate_call_to_action.py, test_filters.py, test_youtube_filter.py  # INALTERADOS (diagnóstico)

tests/
├── fakes/                      # M1: proxies falsos, footage falso, publisher falso; M6: memory_store.py
├── fixtures/daily_run_golden.json   # M1: gravado do código antigo
├── flows/                      # M1: test_daily_run_golden.py, test_daily_run.py; M6: test_publish_slots.py, test_adapters.py
├── capabilities/               # M2..M5: test_writing.py, test_discovery.py, test_import_isolation.py,
│                               #         test_footage_youtube.py, test_footage_local.py, test_rendering.py, ...
├── storage/                    # M6: test_file_store.py
└── (proxies)                   # test_json_reddit_proxy.py, test_pytube_proxy.py, test_caching_youtube_proxy.py,
                                # test_tiktok_*.py INALTERADOS

Justfile                        # M1: sem story-* e generate-reddit*; M5: render-story
config.yaml / config.dev.yaml / config.prod.yaml   # M1: sem blocos de imagem/image_story_bot/prepared;
                                                    # M4/M5: footage_source, rendering_strategy comentados com defaults
docs/                           # M7
```

**Structure Decision**: projeto único existente, com dois pacotes novos que dão nome
às camadas que hoje estão implícitas: `src/capabilities/<nome>/` (um diretório por
capacidade, com `contract.py` ao lado da implementação) e `src/flows/` (o único lugar
com regra de negócio composta). `src/services/` deixa de existir: cada serviço vira
parte da capacidade que o usa. `src/proxies/` continua sendo a borda de I/O e não muda
de contrato, exceto pelo enxugamento de `ILLMProxy`. Prompts sobem para `src/prompts/`
porque são conteúdo editável, não detalhe do proxy.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| `ModelStoryWriter` importa a exceção de rate limit do cliente de modelo | A política de retry do fluxo precisa distinguir erro transitório de bloqueio de conteúdo; hoje isso é feito no bot com `import litellm`. Mover para a capacidade de escrita tira o detalhe do fluxo (FR-011) sem inventar uma hierarquia de erros em todos os proxies | Fazer cada proxy de LLM traduzir exceções em erros de domínio tocaria três proxies e o DSPy, que nem usa litellm diretamente, para o mesmo resultado |
| Re-leitura do post por URL antes de escrever, apesar de a candidata já trazer o post | É o que `prepare_satisfying_story` faz hoje; o post listado e o post lido por URL podem diferir em conteúdo (listagem vs. permalink), e o golden compara o comportamento | Escrever a partir do post da candidata pouparia uma chamada por história, mas quebraria a equivalência sem prova de que o conteúdo é igual; fica anotado como simplificação futura |
| `LocalFolderFootageSource` implementada, e não só o contrato | SC-002 e SC-008 exigem renderizar sem rede; sem uma fonte local, o teste do renderizador e o script de exemplo precisariam de um fake que reimplementa concatenação | Um fake nos testes serviria para SC-002, mas SC-008 pede um fluxo executável pelo operador, e a fonte local é a estratégia mais barata de provar a fronteira de footage |
| Golden com fixture gravado em vez de asserções por caso | SC-001 pede equivalência de um conjunto grande de saídas (mensagens, manifests, linhas de log, chamadas ao publisher) em três modos; escrever isso à mão repetiria o código antigo nos testes | Asserções pontuais não pegariam mudança de ordem de mensagem ou de coluna do log, que é exatamente o que uma refatoração grande tende a quebrar |
| `spec.md` em inglês | Pedido do usuário em inglês; rastreabilidade | Traduzir reescreveria um artefato já validado |
