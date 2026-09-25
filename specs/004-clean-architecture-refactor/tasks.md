# Tasks: Capacidades isoladas e fluxos de negócio finos

**Input**: Design documents from `/specs/004-clean-architecture-refactor/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: incluídos. O spec exige a suíte do fluxo sem rede (SC-002), o golden de
equivalência (SC-001) e testes por capacidade (SC-004, SC-006, SC-007); sem eles os
gates não fecham.

**Organization**: uma fase por milestone do plano. O milestone é a unidade de merge
(1 PR); as tarefas são commits dentro dele. Cada milestone mapeia as user stories do
spec que ele entrega.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência de tarefa aberta)
- **[Story]**: user story do spec (US1..US8)
- Caminhos exatos em cada descrição

## Delivery Plan

| PR | Milestone | Stories | Gate |
|----|-----------|---------|------|
| 1 | M1 — Remover o que não é a rodada diária e gravar o golden | US8 | suíte verde, grep SC-011 vazio fora de `specs/`, golden gravado, `just daily-generate 1` produz manifest `source: auto` |
| 2 | M2 — Modelo de história e capacidade de escrita | US2, US6 (modelo) | testes de escrita e de `Story`; prompt editado aparece no log; template quebrado estoura no boot nomeando o arquivo; golden verde |
| 3 | M3 — Capacidade de descoberta | US4 | testes movidos verdes; import da descoberta < 2 s sem moviepy/whisper/torch; golden verde |
| 4 | M4 — Capacidade de footage | US5 | testes movidos + fonte local; `footage_source: local` renderiza sem YouTube; golden verde |
| 5 | M5 — Capacidade de renderização | US1, US6 (renderização) | 1 parte e 3 partes renderizam com fakes; `render-story` sobre pasta local; golden verde |
| 6 | M6 — Fluxo diário, armazenamento e adaptadores | US3, US7, US6 (agendamento) | golden verde com o fixture inalterado; store em memória; 3 partes em 3 slots; `daily_run.py` ≤ 300 linhas |
| 7 | M7 — Documentação, dependências e limpeza | — | `uv sync` + suíte verde; `black --check`; grep SC-011 vazio em docs |

**Projeção**: 7 PRs.

---

## Phase 1: Setup

- [X] T001 Decidir o destino das alterações não commitadas de `003-polish-review` (`src/services/prepared_story_queue.py`, `tests/test_prepared_story_queue.py`, `specs/003-local-story-prep/{plan,tasks}.md`): commitar na 003 ou descartar; depois criar a branch `004-clean-architecture-refactor` a partir de `main`, copiar `specs/004-clean-architecture-refactor/`, `.specify/feature.json` e a mudança de `AGENTS.md` para ela, e registrar a linha de base `uv run pytest -q` (360 coletados, 1 falha pré-existente em `tests/test_translation_pipeline.py`) na seção Notes deste arquivo

---

## Phase 2: Milestone 1 — Remover o que não é a rodada diária e gravar o golden (US8) — PR 1

**Goal**: o repositório só contém o que a rodada diária usa, e um teste golden
fixa o comportamento atual dos três modos antes de qualquer extração.

**Independent test criteria**:
- `uv run pytest -q` verde.
- `grep -rEi "prepared_stor|two.?part|image.?story|interactive_bot|main_fastapi" --include='*.py' --include='*.md' --include='*.yaml' --include=Justfile . | grep -v '^./specs/'` não retorna nada.
- `tests/fixtures/daily_run_golden.json` existe, foi gravado pelo código antigo e `tests/flows/test_daily_run_golden.py` passa.
- `just daily-generate 1` com `config.dev.yaml` produz `output/daily/story_01.mp4` e `story_01.json` com `"source": "auto"` e sem `part`.

### Remoção

- [X] T002 [P] [US8] Apagar a preparação local e a fila: `scripts/prepare_story.py`, `.claude/skills/prepare-story/SKILL.md` (e o diretório), `src/entities/prepared_story.py`, `src/services/prepared_story_queue.py`, `src/services/prepared_story_validation.py`, `src/proxies/prompts/render.py`, `docs/prepared-stories.md`, `tests/test_prepare_story_cli.py`, `tests/test_prepared_story_package.py`, `tests/test_prepared_story_queue.py`, `tests/test_render_story_prompt.py`, `tests/test_render_two_part_prompt.py`
- [X] T003 [P] [US8] Apagar o formato em duas partes: `src/proxies/prompts/two_part_story.jinja2`, `src/proxies/prompts/revise_story.jinja2`, `src/proxies/examples/two_part_story.yaml`, `scripts/reddit_two_part_history.py`, `tests/test_two_part_story.py`, `tests/services/test_hook_quality.py`, `tests/services/test_content_boundaries.py`
- [X] T004 [P] [US8] Apagar image story, bot interativo e entradas mortas: `bots/image_story_bot.py`, `bots/interactive_bot.py`, `scripts/image_story_video.py`, `scripts/test_image_story.py`, `src/entities/image_story.py`, `src/proxies/prompts/generate_characters.jinja2`, `src/proxies/prompts/generate_image_story.jinja2`, `src/proxies/leonardo_proxy.py`, `src/proxies/leonardo_v2_proxy.py`, `src/proxies/midjourney_proxy.py`, `src/proxies/local_sdxl_proxy.py`, `src/proxies/runpod_comfyui_proxy.py`, `src/proxies/mock_image_proxy.py`, `src/proxies/comfyui_video_proxy.py`, `src/entities/configs/proxies/image_generation.py`, `src/entities/configs/proxies/video_generation.py`, `main.py`, `src/entities/reddit.py`, `src/entities/reddit_history.py`, `src/entities/history.py`, `tests/test_translation_pipeline.py`, `tests/test_transcription_enhance.py`, `tests/script_youtube_download.py`
- [X] T005 [US8] Enxugar `ILLMProxy` em `src/proxies/interfaces.py` para `generate_story`, `evaluate_story`, `generate_hashtags`, `enhance_transcription`; remover `IImageGeneratorProxy` e `IVideoGeneratorProxy`; remover os métodos `generate_two_part_story`, `revise_story`, `generate_characters`, `generate_image_story` e as signatures/helpers correspondentes de `src/proxies/llm_prompt_proxy.py`, `src/proxies/llm_dspy_proxy.py` (`TwoPartTikTokStorySignature`, `GenerateImageStorySignature`) e `src/proxies/mock_llm_proxy.py` (`_find_sentence_boundaries`, `_build_mock_image_story`)
- [X] T006 [US8] Remover a fiação das features apagadas: `ImageGeneratorFactory` e `VideoGeneratorFactory` de `src/proxies/factories.py`; providers `image_generation_proxy`, `portrait_generation_proxy`, `prepared_story_queue` de `src/core/container.py`; campos `image_generation_config` e `portrait_generation_config` de `src/entities/config.py`; `leonardo_api_key`, `runpod_api_key`, `legnext_api_key`, `telegram_image_story_bot_token` de `src/core/secrets.py`; `PreparedStoriesConfig`, o campo `prepared_stories` e `image_story_bot` de `src/entities/configs/bots.py`; `send_image_bytes` de `bots/base.py`
- [X] T007 [US8] Enxugar `src/services/reddit_video_service.py` para `PreparedStory`, `SingleVideoResult`, `scrape_post`, `prepare_satisfying_story`, `generate_satisfying_video_from_story`, `generate_satisfying_video`, `_normalize_marker_word`, `_compute_satisfying_cta_start`, `_render_video_to_bytes` (construtor sem proxies de imagem); remover de `src/services/video_service.py` `generate_image_story_video`, `_build_image_segments`, `_create_ken_burns_clip`, `_create_brush_mask_clip`, `_generate_brush_reveal_map`, `_blur_image_bytes` e os imports de `ImageStory`/PIL que sobrarem; remover `draw_transition_duration` de `src/entities/configs/services/video.py`
- [X] T008 [US8] Enxugar `bots/satisfying_bot.py`: remover `cmd_prepared`, `_queue`, `_mark_done`, `_mark_failed`, `_outcome`, `_PublishError`/`_PublishResult` se ficarem sem uso, `_WorkItem.prepared/part2/queued/story_title` e `parts()`; `_collect_candidates` vira descoberta com `exclude_urls = _scheduled_post_urls(...)`; `_ensure_script` sempre escreve; `_generate_video_for_story` produz um vídeo; `_publish_item` publica um vídeo; `GeneratedVideo` sem `part`, manifest mantém `source: "auto"`; remover os imports de `TwoPartStoryPackage`, `QueuedPackage`, `validate_package`; `/prepared` sai do `main()` e de `_handle_text_command`
- [X] T009 [US8] Limpar configuração, receitas e docs de referência: remover `story-*`, `generate-reddit` e `generate-reddit-fast` do `Justfile`; remover `image_generation_config`, `portrait_generation_config`, `bots.image_story_bot`, o bloco comentado `prepared_stories` e `draw_transition_duration` de `config.yaml`, `config.dev.yaml` e `config.prod.yaml`; remover as seções "Image Story Video", "Two-Part History Video" e "Preparar histórias no laptop" de `README.md`, a seção "Prepared stories" e "Image Generation" de `docs/configuration.md`, a seção "Generate a Reddit Video"/"CLI Options" de `docs/quickstart.md` e o diagrama "Daily Job Flow" com fila de `docs/architecture.md` (a reescrita completa fica para o M7)

### Golden

- [X] T010 [P] [US8] Criar `tests/fakes/__init__.py`, `tests/fakes/proxies.py` (`FakeRedditProxy` com posts fixos, `FakeLLMProxy` com roteiro/avaliação/hashtags/correção determinísticos e uma sequência programável de erros, `FakeSpeechProxy`, `FakeTranscriptionProxy`, `FakeCoverProxy`), `tests/fakes/publisher.py` (`FakePublisher` gravando chamadas e falhando na chamada N) e `tests/fakes/video.py` (`FakeVideoService` que devolve bytes fixos)
- [X] T011 [US8] Mover `tests/test_daily_prepared_flow.py` para `tests/flows/test_daily_run.py` mantendo só `TestGenerateOnly`, `TestScheduledPostUrls`, `TestLoadGeneratedVideos`, `TestPublishFromDirectory` (adaptados ao bot enxuto, sem fila); mover `tests/test_publish_slots.py` para `tests/flows/test_publish_slots.py` e adaptar `TestDailyAutoPublishPipeline` ao bot enxuto; criar `tests/flows/__init__.py`
- [X] T012 [US8] Criar `tests/flows/test_daily_run_golden.py` que roda `run_daily_auto_publish`, `run_daily_generate` e `run_daily_publish` de `bots/satisfying_bot.py` com os fakes (cenário: 5 candidatas; a 2ª com erro transitório na 1ª tentativa; a 3ª bloqueada por filtro; a 1ª publicação falha; meta 3) e compara `{messages, manifests, publish_log_rows (sem created_at), publisher_calls}` com `tests/fixtures/daily_run_golden.json`; opção `--update-golden` em `tests/conftest.py` que regrava o fixture; gravar o fixture e commitar
- [X] T013 [US8] Gate M1: rodar `uv run pytest -q`, o grep de SC-011 (quickstart §1), `uv run python -m bots.satisfying_bot` com `config.dev.yaml` (sobe e para) e `just daily-generate 1`; conferir `source: auto` e ausência de `part` no manifest; registrar o resultado em Notes

**Live verification (milestone gate)**: quickstart §1. Suíte verde, grep vazio fora
de `specs/`, golden gravado e passando, manifest com `source: auto`.

**Checkpoint**: Milestone 1 DONE ✅ (2026-09-25)

---

## Phase 3: Milestone 2 — Modelo de história e capacidade de escrita (US2, US6 modelo) — PR 2

**Goal**: `Story` com N partes é a entidade central; o escritor de produção e um
escritor estático satisfazem o mesmo contrato; os prompts vivem em `src/prompts/` e
são validados no boot.

**Independent test criteria**:
- `ModelStoryWriter` com `FakeLLMProxy` devolve `Story` de 1 parte com título, gênero resolvido pela regra do data-model e `origin` preenchida.
- Erro `429` vira `WriterTransientError`; "content filter" vira `WriterContentBlockedError`; outro vira `WriterError`.
- `StaticStoryWriter` devolve a história registrada sem tocar no LLM.
- `Story` com 3 partes: `cover_title_for` termina em ` - Parte 3`; com 1 parte não tem sufixo.
- Editar `src/prompts/story.jinja2` muda o prompt enviado sem código; template com sintaxe quebrada faz `container.llm_proxy()` estourar nomeando `story.jinja2`.
- Golden verde.

### Modelo

- [X] T014 [P] [US2] Criar `src/entities/story.py` com `StoryOrigin` (`from_post`, `original_markdown`), `StoryPart`, `Story` (`is_multipart`, `cover_title_for`, `story_markdown`, validação de partes não vazias e índices contíguos) e `part_label(language, index)` conforme `data-model.md`
- [X] T015 [P] [US6] Criar `tests/entities/__init__.py` e `tests/entities/test_story.py`: `cover_title_for` com 1 e 3 partes, `part_label` para `pt-br` e `en`, `from_post`, validação (partes vazias, índice fora de ordem)

### Prompts

- [X] T016 [US2] Criar `src/prompts/` movendo `story.jinja2`, `evaluate_story.jinja2`, `generate_hashtags.jinja2`, `enhance_transcription.jinja2` de `src/proxies/prompts/` e `examples/transcription_enhancement.yaml` de `src/proxies/examples/`; criar `src/prompts/__init__.py` e `src/prompts/loader.py` (`render(template_name, **variables)`, `load_examples(name)`, `validate_all()` estourando `TemplateSyntaxError` com o nome do arquivo); apontar `src/proxies/llm_prompt_proxy.py`, `src/proxies/llm_dspy_proxy.py` e `src/proxies/mock_llm_proxy.py` para o loader; apagar `src/proxies/prompts/` e `src/proxies/examples/`
- [X] T017 [P] [US2] Criar `tests/prompts/__init__.py` e `tests/prompts/test_loader.py`: `render` de cada template com variáveis mínimas, `validate_all` verde com os templates reais, `validate_all` estourando com um template inválido num `tmp_path` apontado via monkeypatch do diretório

### Escrita

- [X] T018 [US2] Criar `src/capabilities/__init__.py`, `src/capabilities/writing/__init__.py`, `src/capabilities/writing/contract.py` (`StoryWriter` Protocol, `WriterError`, `WriterTransientError`, `WriterContentBlockedError`), `src/capabilities/writing/model_writer.py` (`ModelStoryWriter(llm)`: `generate_story` → `Story` de 1 parte; resolução de gênero; classificação de erro movida de `_is_transient_error`/`_is_content_filter_error` do bot, incluindo `litellm.RateLimitError`) e `src/capabilities/writing/static_writer.py` (`StaticStoryWriter(stories: dict[str, Story])`)
- [X] T019 [P] [US2] Criar `tests/capabilities/__init__.py` e `tests/capabilities/test_writing.py` cobrindo os critérios de escrita acima com `FakeLLMProxy`
- [X] T020 [US2] Integrar: provider `story_writer` em `src/core/container.py` (usa `history_adaptation_llm_proxy` ou `llm_proxy`, e chama `validate_all()` ao construir `llm_proxy`); `bots/satisfying_bot.py` chama `container.story_writer().write(origin)` em `_prepare_story_with_retries` (retry sobre `WriterTransientError`, skip sobre `WriterContentBlockedError`, sem `import litellm`) e monta `origin` com `StoryOrigin.from_post(service.scrape_post(url))`; `RedditVideoService.generate_satisfying_video_from_story` recebe `Story` (usa `parts[0].text`, `cover_title_for`) e `PreparedStory` + `prepare_satisfying_story` são apagados; atualizar `tests/fakes/` e `tests/flows/` para o novo tipo
- [X] T021 [US2] Gate M2: `specs/004-clean-architecture-refactor/quickstart.md` §2 (suíte, edição de prompt visível no log, template quebrado estoura no boot); golden verde; registrar em Notes de `specs/004-clean-architecture-refactor/tasks.md`

**Live verification (milestone gate)**: quickstart §2.

**Checkpoint**: Milestone 2 DONE ✅ (2026-09-25)

---

## Phase 4: Milestone 3 — Capacidade de descoberta (US4) — PR 3

**Goal**: descoberta é um pacote próprio com contrato, usável sem carregar o stack de vídeo.

**Independent test criteria**:
- Os testes de `tests/services/test_story_finder_service.py` passam movidos sem mudar asserção.
- `find_candidates` não chama `evaluate_story`; `exclude_urls` respeitado; um subreddit falhando não derruba os demais; todos falhando estoura `RuntimeError`.
- Num subprocesso, `import src.capabilities.discovery` não carrega `moviepy`, `whisper`, `torch` nem `playwright`, e leva menos de 2 s.
- Golden verde.

- [X] T022 [US4] Criar `src/capabilities/discovery/__init__.py`, `src/capabilities/discovery/contract.py` (`StoryDiscovery` Protocol com `fetch`, `find_candidates`, `grade`, `find_best_stories`) e `src/capabilities/discovery/reddit_discovery.py` (`RedditStoryDiscovery(reddit, llm, evaluation)` com o conteúdo de `src/services/story_finder_service.py`, `grade` extraído do loop de avaliação, `fetch` = `reddit.get_reddit_post` → `StoryOrigin`); apagar `src/services/story_finder_service.py`
- [X] T023 [US4] Integrar: provider `story_discovery` em `src/core/container.py` (remover `story_finder_service`); `bots/satisfying_bot.py` usa `container.story_discovery()` em `_discover_stories` e `discovery.fetch(url)` no lugar de `service.scrape_post`; `scripts/find_best_stories.py`, `scripts/evaluate_story.py`, `scripts/list_posts.py` passam a usar `container.story_discovery()` (ou `container.reddit_proxy()` onde só listam)
- [X] T024 [P] [US4] Mover `tests/services/test_story_finder_service.py` para `tests/capabilities/test_discovery.py` (imports novos, asserções iguais) e criar `tests/capabilities/test_import_isolation.py` (subprocesso `python -c` que importa a descoberta e imprime os módulos carregados; assert de ausência de `moviepy`/`whisper`/`torch`/`playwright` e de tempo < 2 s)
- [X] T025 [US4] Gate M3: `specs/004-clean-architecture-refactor/quickstart.md` §3; golden verde; registrar em Notes de `specs/004-clean-architecture-refactor/tasks.md`

**Live verification (milestone gate)**: quickstart §3.

**Checkpoint**: Milestone 3 DONE ✅ (2026-09-25)

---

## Phase 5: Milestone 4 — Capacidade de footage (US5) — PR 4

**Goal**: o vídeo de fundo vem de uma `FootageSource`; YouTube+cache e pasta local
são duas implementações do mesmo contrato, escolhidas por configuração.

**Independent test criteria**:
- `tests/services/test_video_service.py` e `test_compilation_rate_limit.py` passam movidos sem mudar asserção.
- `LocalFolderFootageSource` cobre a duração com clipes falsos e estoura `FootageShortfallError` com o déficit quando não cobre.
- `footage_source: local` sem `local_footage_dir` falha na construção do container nomeando a chave.
- `footage_source: local` com dois `.mp4` numa pasta e `just daily-generate 1` produz o vídeo sem menção a YouTube no log.
- Golden verde.

- [X] T026 [US5] Criar `src/capabilities/footage/__init__.py`, `src/capabilities/footage/contract.py` (`Footage`, `FootageShortfallError(needed, got)`, `FootageSource` Protocol) e `src/capabilities/footage/youtube.py` (`YouTubeFootageSource(youtube, video_config)` com `create_youtube_video_compilation`, `_finish_without_network`, `_list_youtube_compilation_video_ids`, `_list_channel_video_ids`, `_youtube_channel_urls` movidos de `src/services/video_service.py`; a `Exception` genérica de pool esgotado vira `FootageShortfallError`)
- [X] T027 [P] [US5] Criar `src/capabilities/footage/local_folder.py` (`LocalFolderFootageSource(directory, video_config)`: lista `.mp4`, embaralha, concatena com `apply_anti_fingerprint` até `min_duration`, `FootageShortfallError` com o déficit)
- [X] T028 [US5] Integrar: `footage_source: Literal["youtube","local"] = "youtube"` e `local_footage_dir: Optional[str]` em `src/entities/configs/services/video.py`; provider `footage_source` em `src/core/container.py` (fábrica que escolhe por config e estoura `ValueError` nomeando `local_footage_dir` quando falta); `src/services/video_service.py` fica só com `generate_video` e constantes; `RedditVideoService._render_video_to_bytes` recebe `footage_source` e chama `compile(min_duration=speech.clip.duration, low_quality=...)`; blocos comentados com os defaults em `config.yaml`, `config.dev.yaml`, `config.prod.yaml`
- [X] T029 [P] [US5] Mover `tests/services/test_video_service.py` (parte de compilação) e `tests/services/test_compilation_rate_limit.py` para `tests/capabilities/test_footage_youtube.py`; criar `tests/capabilities/test_footage_local.py` (clipes falsos via monkeypatch de `VideoClip`, cobertura e déficit) e um teste em `tests/test_container_config.py` para `local` sem diretório; atualizar `tests/fakes/video.py` com um `FakeFootageSource`
- [X] T030 [US5] Gate M4: `specs/004-clean-architecture-refactor/quickstart.md` §4; golden verde; registrar em Notes de `specs/004-clean-architecture-refactor/tasks.md`

**Live verification (milestone gate)**: quickstart §4.

**Checkpoint**: Milestone 4 DONE ✅ (2026-09-25)

---

## Phase 6: Milestone 5 — Capacidade de renderização (US1, US6 renderização) — PR 5

**Goal**: qualquer `Story` mais qualquer `FootageSource` viram `RenderedPart`s por
um `Renderer` escolhido por nome; `RedditVideoService` e `src/services/` deixam de existir.

**Independent test criteria**:
- 1 parte com fakes e sem rede → 1 `RenderedPart` com vídeo, áudio, legendas JSON censuradas e capa; título da capa sem sufixo; `cta_start` calculado como hoje.
- 3 partes → 3 `RenderedPart` com ` - Parte N` na capa (SC-004, renderização).
- `select_renderer("animation", ...)` estoura nomeando a estratégia e listando as disponíveis.
- `just render-story /tmp/story.json /tmp/bg` produz um mp4 usando só `container.renderer()`; `scripts/render_story.py` ≤ 60 linhas.
- Golden verde.

- [X] T031 [P] [US1] Criar `src/entities/rendered.py` com `RenderedPart(part, cover_title, video, audio, captions_json, cover_png)`
- [X] T032 [P] [US1] Criar `src/capabilities/rendering/__init__.py`, `src/capabilities/rendering/contract.py` (`Renderer` Protocol com `name` e `render`) e `src/capabilities/rendering/registry.py` (`select_renderer(name, renderers)` com `KeyError` listando os nomes)
- [X] T033 [US1] Mover para `src/capabilities/rendering/`: `speech.py` (de `src/services/speech_service.py`), `captions.py` (`captions_service.py`), `cover.py` (`cover_service.py`), `compose.py` (`VideoService.generate_video` como `VideoComposer(video_config)` com `CROSSFADE_DURATION`), `censor.py` (`text_censor.py`), `cta.py` (`_normalize_marker_word`, `CTA_START_WORDS`, `compute_cta_start`); mover `src/services/tiktok_caption.py` para `src/capabilities/publishing/hashtags.py` (`normalize_hashtags` como função; classe vem no M6) com `src/capabilities/publishing/__init__.py`; atualizar imports em `src/core/container.py` e `bots/satisfying_bot.py`
- [X] T034 [US1] Criar `src/capabilities/rendering/narration_over_footage.py` (`NarrationOverFootageRenderer(speech, captions, cover, footage, composer, censor, video_config)`, `name = "narration-over-footage"`, `render(story, low_quality)`: para cada parte, fala → legendas corrigidas com `part.text` → `compute_cta_start` → censura de legendas → capa com `censor(story.cover_title_for(part))` e a atribuição da origem → `footage.compile(min_duration=duração da fala)` → `composer.compose(...)` → mp4 em bytes via `tempfile` + `asyncio.to_thread`, fps/ffmpeg da config); corpo movido de `generate_satisfying_video_from_story` + `_render_video_to_bytes`
- [X] T035 [US1] Integrar: `rendering_strategy: Literal["narration-over-footage"] = "narration-over-footage"` em `src/entities/configs/services/video.py`; providers `renderers` (dict) e `renderer` (`select_renderer`) em `src/core/container.py`; apagar `src/services/reddit_video_service.py`, `src/services/video_service.py` e o pacote `src/services/`; `bots/satisfying_bot.py` chama `container.renderer().render(story)` em `_generate_video_for_story` e no `GenerationQueue._process` (URL → vídeo), gravando `story_NN.mp4` para a parte 1 e `story_NN_p{k}.mp4` para `k ≥ 2`, manifest com `part` só quando multipart; `SingleVideoResult` some
- [X] T036 [P] [US1] Criar `tests/capabilities/test_rendering.py` (1 parte, 3 partes, censura de legendas e título, `cta_start`, `select_renderer` desconhecido) com `FakeSpeechProxy`, `FakeTranscriptionProxy`, `FakeCoverProxy`, `FakeFootageSource` e um `FakeComposer`; mover `tests/services/test_video_clip_duration.py`, `tests/services/test_cover_layout.py`, `tests/services/test_text_censor.py`, `tests/services/test_tiktok_caption.py` e a parte de `generate_video` de `tests/services/test_video_service.py` para `tests/capabilities/` (`test_compose.py`, `test_censor.py`, `test_hashtags.py`, …); mover `tests/services/test_clean_json.py` para `tests/proxies/test_clean_json.py`; apagar `tests/services/`
- [X] T037 [US1] Criar `scripts/render_story.py` (≤ 60 linhas: lê um JSON de `Story` conforme quickstart §5, constrói `Story`, chama `container.renderer().render`, grava `output/render/part{k}.mp4`) e a receita `render-story story_json footage_dir` no `Justfile` (exporta `footage_source=local` via `CONFIG_PATH` ou variável de ambiente documentada no script)
- [X] T038 [US1] Gate M5: `specs/004-clean-architecture-refactor/quickstart.md` §5; golden verde; registrar em Notes de `specs/004-clean-architecture-refactor/tasks.md`

**Live verification (milestone gate)**: quickstart §5.

**Checkpoint**: Milestone 5 DONE ✅ (2026-09-25)

---

## Phase 7: Milestone 6 — Fluxo diário, armazenamento e adaptadores (US3, US7, US6 agendamento) — PR 6

**Goal**: `DailyRun` é o único lugar com regra de negócio composta; o estado passa por
`RunStore`; o bot e o CLI são adaptadores; o golden passa sem mudar o fixture.

**Independent test criteria**:
- `tests/flows/test_daily_run_golden.py` passa apontado para `DailyRun` com o fixture gravado no M1 intacto (SC-001).
- `DailyRun` com `InMemoryRunStore` produz os mesmos manifests e linhas de log que com `FileRunStore` (SC-006).
- Os três modos rodam sem rede (SC-002).
- Um `DailyRun` falso prova que o bot (`/autopost 2`, job diário) e o CLI (`--count 2`, `--generate-only`, `--publish-only DIR`) chamam o mesmo método com os mesmos argumentos.
- História de 3 partes → 3 vídeos em 3 slots consecutivos, 3 linhas no log, 1 na meta; falha ao renderizar qualquer parte → nada publicado (SC-004, agendamento).
- Manifest antigo sem `source` e sem `part` carrega (FR-019, SC-012).
- `wc -l src/flows/daily_run.py` ≤ 300 e `grep -nE "telegram|argparse|os\.path|open\("` vazio nele (SC-009).

### Armazenamento

- [ ] T039 [P] [US7] Criar `src/entities/generated_video.py` com `GeneratedVideo(video_path, title, summary, post_url, source="auto", part=None)` movido de `bots/satisfying_bot.py`
- [ ] T040 [US7] Criar `src/storage/__init__.py`, `src/storage/contract.py` (`PublishLogEntry`, `RunStore` Protocol) e `src/storage/files.py` (`FileRunStore(publish_log_path)` com `save_manifest`, `load_manifests`, `append_publish_log`, `scheduled_post_urls` movidos de `_save_manifest`, `load_generated_videos`, `_append_publish_log`, `_scheduled_post_urls` do bot, mesmos caminhos, campos e ordem de colunas)
- [ ] T041 [P] [US7] Criar `tests/fakes/memory_store.py` (`InMemoryRunStore`), `tests/storage/__init__.py` e `tests/storage/test_file_store.py` (manifest com e sem `part`, manifest antigo sem `source`/`part` carrega, mp4 ausente é pulado, CSV com cabeçalho e ordem de colunas, `scheduled_post_urls` só conta `scheduled`, arquivo ausente → vazio)

### Fluxo

- [ ] T042 [P] [US3] Criar `src/flows/__init__.py`, `src/flows/publish_slots.py` (`next_publish_slot`, `compute_publish_slots`, `_parse_slot_times` movidos do bot) e `src/flows/progress.py` (`Progress` type alias, `RunLock` com `locked`/`__aenter__`); mover os testes de slots de `tests/flows/test_publish_slots.py` para importar de `src.flows.publish_slots`
- [ ] T043 [P] [US3] Adicionar `HashtagSuggester(llm, defaults, language)` com `suggest(title, summary)` e `normalize(raw)` em `src/capabilities/publishing/hashtags.py`; provider `tiktok_publisher` em `src/core/container.py` (construção movida de `_build_tiktok_publisher`) e provider `hashtag_suggester`
- [ ] T044 [P] [US3] Criar `src/entities/configs/flows.py` com `DailyRunConfig(count, publish_slots_local, publish_min_lead_minutes, publish_hashtags, low_quality, language, story_retry_max=3, story_retry_base_delay=5)` e `from_main_config(config)` lendo `bots.satisfying_bot` e `language`
- [ ] T045 [US3] Criar `src/flows/daily_run.py` com `DailyRun(discovery, writer, renderer, publisher, hashtags, store, config, progress, now)` e `generate`, `publish`, `run` conforme `contracts/flow.md`: meta, exclusão pelo log, `fetch` + `write` com retry/backoff e skips, `render` tudo-ou-nada, `story_NN[_pk].mp4` + manifest via store, hashtags uma vez por história, parte k no slot seguinte à k-1, linhas `scheduled`/`failed`, mensagens idênticas às do golden; ≤ 300 linhas; sem Telegram, argparse, `os.path` ou `open(`
- [ ] T046 [US3] Adicionar `daily_run = providers.Factory(DailyRun, ...)` em `src/core/container.py` recebendo `progress` como argumento e `DailyRunConfig.from_main_config(main_config)`
- [ ] T047 [US3] Reescrever `bots/satisfying_bot.py` como adaptador (~250 linhas): `/start`, URL → vídeo pela fila de jobs (`discovery.fetch` → `writer.write` → `renderer.render` → `send_audio_bytes`/`send_video_bytes`), `/autopost [n]` e `_daily_find` chamando `container.daily_run(progress=send_to_chat).run(count=n)` sob `RunLock` com a mensagem "Já existe um fluxo de auto-post em andamento."; remover `/find`, `handle_find_generate`, `handle_retry`, `_format_find_message`, `_format_bar`, `_parse_subreddits`, `_find_url_store`, `LLM_LABELS`, `run_daily_*`, `load_generated_videos`, `_collect_candidates`, `_ensure_script`, `_generate_video_for_story`, `_publish_*`, `_is_*_error`, `_truncate_error`
- [ ] T048 [US3] Reescrever `scripts/daily_auto_publish.py` como adaptador: `--count`, `--output-dir`, `--generate-only`, `--publish-only DIR` chamando `container.daily_run(progress=print_line)` nos três modos (`publish` recebe `container.run_store().load_manifests(DIR)`), mesmos códigos de saída
- [ ] T049 [US3] Testes: apontar `tests/flows/test_daily_run_golden.py` para `DailyRun` com os fakes e `InMemoryRunStore`/`FileRunStore` (fixture inalterado); reescrever `tests/flows/test_daily_run.py` sobre `DailyRun` (generate-only, publish-only, retry transitório, bloqueio por filtro, falha de publicação pula e mantém o cursor de slot, `test_three_part_story_schedules_consecutive_slots`, `test_three_part_render_failure_publishes_nothing`, store em memória vs arquivos); criar `tests/flows/test_adapters.py` com um `DailyRun` falso para `cmd_autopost`, `_daily_find` e o `main()` do CLI; adicionar `tests/flows/test_daily_run_shape.py` (linhas ≤ 300 e grep de termos proibidos)
- [ ] T050 [US3] Gate M6: quickstart §6 (suíte, `wc -l`, `grep`, `just daily-generate 1`, `just daily-publish-only output/daily`); no servidor quando disponível, `just deploy` e `just prod-daily-generate 1`; registrar em Notes

**Live verification (milestone gate)**: quickstart §6.

**Checkpoint**: Milestone 6 DONE

---

## Phase 8: Milestone 7 — Documentação, dependências e limpeza final — PR 7

**Goal**: a documentação descreve a estrutura que existe; dependências sem uso saem;
os critérios de sucesso ficam registrados no plano.

- [ ] T051 [P] Reescrever `docs/architecture.md`: árvore real de `src/` (entities, prompts, proxies, capabilities/*, storage, flows), diagrama do `DailyRun`, como registrar uma estratégia de renderização, uma fonte de footage ou um store alternativo, e o papel dos adaptadores
- [ ] T052 [P] Atualizar `docs/configuration.md` (`footage_source`, `local_footage_dir`, `rendering_strategy`; remover restos de imagem e prepared), `docs/quickstart.md` (só rodada diária e `render-story`) e `README.md` (seções restantes coerentes com as receitas do `Justfile`)
- [ ] T053 Revisar `pyproject.toml` com `grep -rn "<pacote>" src bots scripts tests` por dependência e remover as sem uso (candidatas: `coqui-tts`, `azure-cognitiveservices-speech`, `fastapi`, `uvicorn`, `python-multipart`, `ollama`, `anthropic`, `google-api-python-client`); `uv lock`; `uv sync`; suíte verde
- [ ] T054 Revisar o diff acumulado dos PRs 1 a 6 contra a constituição (fail fast: nenhum `except Exception: continue` novo; camadas: `grep -rn "from src.proxies" src/flows` vazio, `grep -rn "from bots\|telegram" src` vazio) e corrigir o que aparecer
- [ ] T055 Rodar quickstart §7 e registrar em `specs/004-clean-architecture-refactor/plan.md` a seção "Verificação pós-implementação" com a tabela SC-001..SC-012 e o que ficou pendente do servidor

**Live verification (milestone gate)**: quickstart §7. `uv sync` + suíte verde;
`black --check`; grep SC-011 vazio em `docs/`, `README.md`, `AGENTS.md`.

**Checkpoint**: Milestone 7 DONE

---

## Dependencies & Execution Order

### Milestones

- **M1** (US8) → **M2** (US2, US6 modelo) → **M3** (US4) → **M4** (US5) → **M5** (US1, US6 renderização) → **M6** (US3, US7, US6 agendamento) → **M7**.
- Cada milestone começa só depois que o gate do anterior passou. A rodada diária tem que funcionar pelo bot ao fim de cada um (M1 a M5 pelo bot antigo apontado para as capacidades novas; M6 pelo `DailyRun`).
- M3 e M4 são independentes entre si e poderiam ser invertidos; a ordem escolhida deixa o `RedditVideoService` como o último consumidor a ser apagado no M5.

### Dentro dos milestones

- M1: T002, T003, T004 em paralelo; T005 → T006 → T007 → T008 → T009 em sequência (cada um destrava imports do seguinte); T010 em paralelo com a remoção; T011 depois de T008; T012 depois de T010 e T011; T013 por último.
- M2: T014 e T015 em paralelo; T016 e T017 em paralelo; T018 depois de T014; T019 depois de T018; T020 depois de T016 e T018; T021 por último.
- M3: T022 → T023; T024 em paralelo com T023; T025 por último.
- M4: T026 e T027 em paralelo; T028 depois de ambos; T029 em paralelo com T028; T030 por último.
- M5: T031 e T032 em paralelo; T033 → T034 → T035; T036 em paralelo com T035; T037 depois de T035; T038 por último.
- M6: T039, T041, T042, T043, T044 em paralelo; T040 depois de T039; T045 depois de T040, T042, T043, T044; T046 → T047 e T048 (paralelos) → T049 → T050.
- M7: T051 e T052 em paralelo; T053 → T054 → T055.

### Parallel Example: Milestone 1

```bash
# Remoção em três frentes sem conflito de arquivo:
Task: "T002 Apagar a preparação local e a fila"
Task: "T003 Apagar o formato em duas partes"
Task: "T004 Apagar image story, bot interativo e entradas mortas"
# Ao mesmo tempo, os fakes que o golden vai usar:
Task: "T010 Criar tests/fakes/"
```

### Parallel Example: Milestone 6

```bash
Task: "T039 GeneratedVideo em src/entities/generated_video.py"
Task: "T041 InMemoryRunStore e testes do store"
Task: "T042 publish_slots.py e progress.py"
Task: "T043 HashtagSuggester e providers do publisher"
Task: "T044 DailyRunConfig"
```

---

## Implementation Strategy

### MVP: Milestone 1

O M1 é o PR que mais reduz risco pelo menor custo: apaga cerca de metade do código,
deixa o bot equivalente ao de hoje com fila vazia e grava o golden. Depois dele o
servidor já pode receber um deploy menor e igual em comportamento.

### Entrega incremental

1. M1: remover e fixar o comportamento (deploy possível).
2. M2 a M5: uma capacidade por PR, o bot antigo consumindo cada uma; o golden é a
   prova de que nada mudou (deploy possível a cada PR).
3. M6: o fluxo novo substitui o miolo do bot; o fixture do golden não muda.
4. M7: documentação e dependências.

### Rollback

Cada PR é revertível sozinho até o M5, porque só move código e mantém o bot como
consumidor. O M6 é o único que muda a forma do bot; se for revertido, o M5 continua
funcionando.

---

## Notes

- Linha de base (T001, 2026-09-25): as alterações de `003-polish-review` foram
  commitadas lá e abertas como PR #8; a branch `004-clean-architecture-refactor` saiu de
  `main` (`ec6d0c5`). `uv run pytest -q` em `main` → `1 failed, 357 passed` (358
  coletados; os 360 do T001 contavam os dois testes do PR #8). A falha é a
  pré-existente `tests/test_translation_pipeline.py::test_pipeline`.
- Gate M1 (T013, 2026-09-25):
  - `uv run pytest -q` → **201 passed**, 0 falhas (a falha pré-existente saiu com o
    arquivo no T004). `uv run black --check src scripts tests bots` limpo.
  - Grep do SC-011 (quickstart §1) fora de `specs/` → nenhuma linha.
  - Golden: `tests/fixtures/daily_run_golden.json` gravado com `--update-golden` a
    partir do bot enxuto e passando. **Equivalência com o código de antes**: o mesmo
    teste e o mesmo fixture rodados num worktree de `main` (bot com a fila, fila vazia
    em `tmp`, proxies de imagem anulados) → passou. O bot enxuto se comporta
    exatamente como o de `main` com a fila vazia nos três modos.
  - O golden registra dois comportamentos atuais que o M6 tem de manter: depois de
    uma falha de publicação o cursor de slot não avança (a próxima história pega o
    mesmo slot) e só linhas `scheduled` do log excluem posts da descoberta.
  - Bot: `bots.satisfying_bot.main()` com `config.dev.yaml` e `run_polling`
    neutralizado registra `ConversationHandler`, `/find`, `/autopost`, os dois
    callbacks e o job `_daily_find`; sem `/prepared`. Não houve polling real porque o
    bot de produção estava ativo no servidor com o mesmo token.
  - `daily-generate 1` com `config.dev.yaml`: rodado com todos os proxies reais
    (Reddit JSON, LLM mock, edge-tts, whisper local, capa Playwright) e só o
    `VideoService` trocado pelo `FakeVideoService` — sem download do YouTube e sem
    render, conforme a regra de não renderizar vídeo no laptop. 97 s; 34 candidatas;
    narração de 192 s; 633 palavras de legenda; `cta_start` 189,52 s; manifest
    `story_01.json` com `"source": "auto"` e sem `part`.
  - **Pendente**: o render real (footage do YouTube + moviepy) não foi exercitado
    neste gate; fica para o servidor (`just deploy` + `just prod-daily-generate 1`)
    quando o PR for aceito.
- Gate M2 (T021, 2026-09-25):
  - `uv run pytest tests/capabilities/test_writing.py tests/flows -q` → **45 passed**;
    `uv run pytest -q` → **232 passed** (201 do M1 + 10 de `Story`, 7 do loader,
    14 da escrita). `black --check` limpo.
  - Golden: `tests/flows/test_daily_run_golden.py` passa com o fixture do M1
    intacto. Ele já passa pelo `ModelStoryWriter` real do container sobre o
    `FakeLLMProxy`, então cobre a classificação de erro (429 → retry,
    "content filter" → pula) de ponta a ponta.
  - Prompt editável (SC-003): `# VOICE` → `# VOICE PORTAOMARCADOR` em
    `src/prompts/story.jinja2`; `daily_auto_publish.py --generate-only --count 1`
    com `config.dev.yaml` e proxies reais (Reddit JSON, LLM mock, edge-tts, whisper,
    Playwright), só o `VideoService` trocado pelo `FakeVideoService` (regra de não
    renderizar no laptop): 33 s, 34 candidatas, a palavra aparece 1× no log
    (`Mock LLM story prompt:`). O `MockLLMProxy` agora renderiza e loga o prompt de
    história para isso ser visível em dev; o `PromptLLMProxy` loga em DEBUG.
    Manifest com `source: auto`, sem `part`, `summary` vindo da avaliação.
  - Template quebrado: `printf '{%% if %%}' >> src/prompts/story.jinja2` →
    `container.llm_proxy()` estoura `TemplateSyntaxError: story.jinja2: Expected an
    expression...` (arquivo e linha 74), exit 1.
  - Mudanças de comportamento conscientes: (1) um erro ao reler o post do Reddit
    antes de escrever não é mais re-tentado, só `WriterTransientError` é
    (`contracts/flow.md` §3); antes, um 429 do Reddit nessa leitura era re-tentado.
    (2) O `DSPyLLMProxy` passa a carregar os exemplos de correção de transcrição:
    o caminho antigo (`proxies/prompts/examples/`) nunca existiu. Nenhum config do
    repositório usa DSPy.
- Gate M3 (T025, 2026-09-25):
  - `uv run pytest tests/capabilities/test_discovery.py
    tests/capabilities/test_import_isolation.py -q` → **12 passed** (os 9 testes
    movidos com as asserções iguais, mais `grade` com falha → nota 0 e `Erro`, e
    `fetch` → `StoryOrigin`); `uv run pytest -q` → **235 passed**. `black --check`
    limpo.
  - Golden: `tests/flows/test_daily_run_golden.py` passa com o fixture do M1
    intacto; ele já passa pela `RedditStoryDiscovery` real do container (busca,
    avaliação e `fetch`) sobre o `FakeRedditProxy`.
  - Isolamento (SC-007): `time uv run python -c "import src.capabilities.discovery"`
    → 0,25 s; `sys.modules` sem `moviepy`/`whisper`/`torch`/`playwright` (`[]`).
    O teste de isolamento foi conferido às avessas: com `import moviepy` no
    `__init__` da descoberta ele falha.
  - `CONFIG_PATH=config.dev.yaml uv run python scripts/find_best_stories.py
    --top-per-sub 2` contra o Reddit real (proxy JSON, avaliação pelo LLM mock):
    28 s, exit 0, 15 histórias de 8 subreddits. `scripts/evaluate_story.py <url>`
    lê o post por `discovery.fetch` e avalia (87/100); de passagem, o `r/r/` duplicado
    que ele imprimia no nome da comunidade foi corrigido.
  - Decisões: (1) `RedditVideoService.scrape_post` e o `reddit_proxy` do serviço
    foram apagados — `discovery.fetch` é o único caminho URL → origem.
    (2) `find_best_stories` exige `language` (contrato); o default português some.
    (3) `scripts/evaluate_story.py` usa `fetch` mas chama `llm.evaluate_story`
    direto, não `grade`: `grade` transforma falha em nota 0 para manter a lista, e
    num CLI de uma história o operador quer ver o erro. `scripts/list_posts.py` só
    lista e continua no `reddit_proxy`.
  - `docs/architecture.md` ainda cita `story_finder_service.py`; a reescrita é do M7
    (T051).
- Gate M4 (T030, 2026-09-25):
  - `uv run pytest tests/capabilities/test_footage_youtube.py
    tests/capabilities/test_footage_local.py tests/test_container_config.py
    tests/flows/test_daily_run_golden.py -q` → **24 passed** (os 12 testes movidos
    de `test_video_service.py` e `test_compilation_rate_limit.py`, mais o pool
    esgotado → `FootageShortfallError(100, 45)`, 7 da pasta local, 3 do container,
    o golden); `uv run pytest -q` → **246 passed**. `black --check` limpo.
  - Golden: passa com o fixture do M1 intacto; o container agora recebe um
    `FakeFootageSource` e o `FakeVideoService` só compõe.
  - `footage_source: local` (`config.dev.yaml` com `local_footage_dir` apontando para
    uma pasta com os 7 `*-lq.mp4` do cache; os dois maiores somam ~119 s, menos que a narração do
    dev, 192 s no gate do M1) e `daily_auto_publish.py --generate-only --count 1` com proxies reais
    (Reddit JSON, LLM mock, edge-tts, whisper, Playwright) e a
    `LocalFolderFootageSource` real abrindo os arquivos; só o `VideoService` trocado
    pelo `FakeVideoService` (regra de não renderizar no laptop): 133 s, exit 0,
    `Compiled 233.8s of local footage from 6 clip(s)`, `grep -ci "pytube\|youtube"`
    no log → **0**. Manifest `story_01.json` com `source: auto`, sem `part`.
  - `footage_source: local` sem `local_footage_dir`: `daily_auto_publish.py` e
    `import bots.satisfying_bot` saem com `ValidationError: ...
    services.video_config.local_footage_dir is required when footage_source is
    'local'` em 8 s, antes de qualquer rede.
  - Decisões: (1) a checagem de `local_footage_dir` ficou num `model_validator` do
    `VideoConfig`, não no provider como o T028 dizia: assim o bot recusa o config no
    boot em vez de na primeira renderização, horas depois; o provider virou um
    `providers.Selector` que só constrói a fonte escolhida. (2) `Footage` ganhou
    `sources` (ids ou nomes de arquivo) no lugar do `downloaded_bytes` do
    `YouTubeCompilationResult`: ninguém lia os bytes, que seguravam cada vídeo baixado
    em memória até o fim da renderização. As duas asserções sobre
    `downloaded_bytes` passaram a comparar `sources` com os mesmos ids. (3)
    `create_youtube_video_compilation` virou `compile` (o contrato). (4) Na pasta
    local, um `.mp4` sem duração estoura nomeando o arquivo (a pasta é curada pelo
    operador); no YouTube continua pulado. (5) `VideoService` perdeu o
    `youtube_proxy` e as constantes mortas do image story (`KEN_BURNS_*`, `BRUSH_*`).
  - **Pendente**: o render real com `footage_source: local` (moviepy sobre os clipes
    locais) não foi exercitado no laptop; o caminho `youtube` padrão continua o
    mesmo código, movido, e fica para o servidor (`just deploy` +
    `just prod-daily-generate 1`).
- Gate M5 (T038, 2026-09-25):
  - `uv run pytest tests/capabilities/test_rendering.py tests/flows/test_daily_run_golden.py -q`
    → **11 passed** (1 parte com todos os artefatos, `test_three_parts` com
    ` - Parte N` na capa, censura de título e legendas, falha numa parte derruba o
    render inteiro, 4 de `compute_cta_start` migrados, `select_renderer`
    desconhecido e conhecido; o golden). `uv run pytest -q` → **257 passed**.
    `black --check` limpo. `src/services/` e `tests/services/` não existem mais.
  - Golden: passa com o fixture do M1 intacto (`git diff tests/fixtures/` vazio); o
    container agora recebe um `FakeComposer` no lugar do `FakeVideoService`, e o
    bot passa pelo `NarrationOverFootageRenderer` real.
  - SC-008: `scripts/render_story.py` tem **60 linhas** e só usa
    `container.renderer()` e o loader de `Story`. Rodado com `config.dev.yaml` sobre
    o JSON do quickstart §5 e uma pasta com dois `*-lq.mp4` do cache: edge-tts,
    whisper local, capa pelo `PlaywrightCoverProxy` (PNG de 74 KB), a
    `LocalFolderFootageSource` real abrindo os arquivos; só o `VideoComposer`
    trocado pelo `FakeComposer` (regra de não renderizar no laptop). 5,8 s, exit 0,
    `output/render/part1.mp4` escrito, narração de 7,39 s, 29 palavras de legenda,
    `grep -ci "pytube\|youtube"` → 0. O `cta_start` caiu no fallback
    (antepenúltima palavra, 5,96 s) porque o whisper ouviu "curtei" e o LLM mock
    não corrige a transcrição; com o LLM real a correção devolve "Curta".
  - Bot: `daily_auto_publish.py --generate-only --count 1` com proxies reais
    (Reddit JSON, LLM mock, edge-tts, whisper, Playwright), `footage_source: local`
    numa cópia do `config.dev.yaml` e só o composer falso: 88 s, exit 0, mensagens
    iguais às do M4, manifest `story_01.json` com `source: auto` e sem `part`.
    Uma primeira tentativa por engano com `footage_source: youtube` pegou HTTP 429
    do YouTube em todas as candidatas e foi interrompida na #13; serviu de prova de
    que a falha de render pula a candidata sem gravar nada.
  - SC-005: o diff do M5 não toca `src/capabilities/{discovery,writing,footage}`.
  - Decisões: (1) `RenderedPart.cover_title` é o título censurado da capa, como
    o data-model pede; o título do manifest (descrição do TikTok) continua sem
    censura e vem de `story.cover_title_for(part)` no bot, como antes.
    (2) `VideoService.generate_video` virou `VideoComposer.compose`;
    `CROSSFADE_DURATION` virou constante de módulo. (3) O bot já grava
    `story_NN_p{k}.mp4` e o manifest com `part` só em história multipartes
    (teste novo em `tests/flows/test_daily_run.py`); a meta conta histórias; no
    auto-post a parte k vai no slot seguinte ao da k-1 e uma falha pula o resto da
    história. Hashtags continuam uma chamada por vídeo — uma por história é do M6.
    (4) O teste único de `tests/services/test_video_service.py` (era de
    `VideoClip.ajust_duration`, não de `generate_video`) foi para
    `tests/capabilities/test_video_clip_duration.py`. (5) `render_story.py` troca
    a fonte de footage sobrescrevendo o `main_config` do container com
    `footage_source: local` e a pasta do argumento, em vez de variável de
    ambiente. (6) `log_function_call` e `log_progress_event` de
    `src/core/logging_config.py`, sem uso e presos a `src.services`, saíram.
  - **Pendente**: o render real (moviepy) pelo `NarrationOverFootageRenderer` não
    foi exercitado no laptop; o corpo é o de `generate_satisfying_video_from_story`
    + `_render_video_to_bytes`, movido. Fica para o servidor (`just deploy` +
    `just prod-daily-generate 1`), junto com os pendentes do M1 e do M4.
- Gates (T050, T055): a preencher com data, comando e resultado.
- O golden é regravado apenas com `--update-golden` e com o diff revisado no PR; um
  fixture alterado no M6 é sinal de mudança de comportamento, não de progresso.
