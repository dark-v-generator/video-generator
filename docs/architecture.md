# Architecture Overview

The application does one thing every day: find Reddit stories, write a narration
script for each, render it as a vertical video and schedule it on TikTok. That
**daily run** is the only business flow. Everything else is a piece it combines:

- a **story model** (`Story` with one or more parts) at the centre;
- five **capabilities**, each behind a contract: discovery, writing, footage,
  rendering and publishing;
- a **storage boundary** for what survives between runs (manifests and the
  publish log);
- two **adapters**, the Telegram bot and the command line, that start the run and
  show its progress.

Dependencies point inwards: adapters → flow → capabilities → proxies, and every
layer may use the entities. The flow imports contracts only; the container is the
one place that picks implementations.

```
 bots/satisfying_bot.py      scripts/daily_auto_publish.py        adapters
            │                          │
            └────────────┬─────────────┘
                         ▼
                src/flows/daily_run.py                            business flow
                         │
      ┌──────────┬───────┼────────┬─────────────┬───────────┐
      ▼          ▼       ▼        ▼             ▼           ▼
  discovery   writing  rendering  publishing  src/storage         capabilities
      │          │       │  └──▶ footage        │               + storage
      ▼          ▼       ▼          ▼           ▼
                 src/proxies/  (Reddit, LLM, TTS, Whisper,        I/O edges
                 Playwright, YouTube, TikTok agent)
```

## Project Structure

```
src/
├── core/
│   ├── container.py          # Dependency injection: builds every piece from config.yaml
│   ├── secrets.py            # API keys and tokens from .env
│   └── logging_config.py
├── entities/                 # Plain data, no I/O
│   ├── story.py              # StoryOrigin, StoryPart, Story (N parts), part_label
│   ├── rendered.py           # RenderedPart: video, audio, captions and cover of one part
│   ├── generated_video.py    # GeneratedVideo: what a manifest records
│   ├── reddit_post.py, story_candidate.py, captions.py, cover.py,
│   │   language.py, speech_voice.py, transcription.py
│   ├── config.py             # MainConfig = proxies + services + bots + evaluation + language
│   ├── configs/
│   │   ├── proxies/          # One config model per proxy type
│   │   ├── services/         # video (footage_source, rendering_strategy, ...), captions, censorship
│   │   ├── bots.py           # bots.satisfying_bot: schedule, count, slots, hashtags
│   │   └── flows.py          # DailyRunConfig, gathered from bots.satisfying_bot + language
│   └── editor/               # MoviePy wrappers (VideoClip, AudioClip, CaptionsClip, ImageClip)
├── prompts/                  # Editable prompt templates, validated when the container starts
│   ├── story.jinja2, evaluate_story.jinja2, generate_hashtags.jinja2,
│   │   enhance_transcription.jinja2
│   ├── examples/             # Few-shot examples (transcription correction)
│   └── loader.py             # render(name, **vars), load_examples(name), validate_all()
├── proxies/                  # External integrations
│   ├── interfaces.py         # IRedditProxy, ILLMProxy, ISpeechProxy, ITranscriptionProxy,
│   │                         # IYouTubeProxy, ICoverProxy, ITikTokPublisherProxy
│   ├── factories.py          # Picks the implementation from the config's `type`
│   └── ...                   # json/bs4 Reddit, prompt/dspy/mock LLM, edge-tts, ElevenLabs,
│                             # local/OpenAI Whisper, Playwright cover, pytube + cache, TikTok agent
├── capabilities/
│   ├── discovery/            # StoryDiscovery → RedditStoryDiscovery
│   ├── writing/              # StoryWriter → ModelStoryWriter, StaticStoryWriter
│   ├── footage/              # FootageSource → YouTubeFootageSource, LocalFolderFootageSource
│   ├── rendering/            # Renderer → NarrationOverFootageRenderer (+ speech, captions,
│   │                         # cover, compose, censor, cta, registry)
│   └── publishing/           # HashtagSuggester; the contract is ITikTokPublisherProxy
├── storage/
│   ├── contract.py           # RunStore, PublishLogEntry
│   └── files.py              # FileRunStore: output/daily/*.json + .storage/tiktok_publish_log.csv
└── flows/
    ├── daily_run.py          # DailyRun: generate, publish, run
    ├── publish_slots.py      # next_publish_slot, compute_publish_slots
    └── progress.py           # Progress callback type, RunLock, short_error
bots/
├── base.py                   # Telegram helpers (allowed users, sending audio and video)
└── satisfying_bot.py         # Telegram adapter: daily job, /autopost, URL → video
scripts/
├── daily_auto_publish.py     # CLI adapter: full run, --generate-only, --publish-only DIR
├── render_story.py           # A hand-written story JSON + a folder of clips → output/render/
├── find_best_stories.py, evaluate_story.py, list_posts.py   # Discovery diagnostics
└── publish_tiktok.py, tiktok_repl.py, ...                    # TikTok publisher tooling
tests/
├── fakes/                    # Fake proxies, publisher, footage, composer, InMemoryRunStore
├── fixtures/daily_run_golden.json
├── flows/                    # Golden test, DailyRun, adapters, slots, module shape
├── capabilities/             # One file per capability (+ import isolation of discovery)
├── storage/, entities/, prompts/, proxies/
```

## The Daily Run

`DailyRun` (`src/flows/daily_run.py`) holds every business decision, in the order
it is taken. It receives its capabilities, a `RunStore`, a `DailyRunConfig` and a
`progress` callback; it knows nothing about Telegram, argv or file layout.

```
 store.scheduled_post_urls() ──▶ discovery.find_best_stories(exclude_urls=…)
                                          │ ranked candidates (spares replace skips)
                                          ▼
   for each candidate, until the day's target is met:
   ┌──────────────────────────────────────────────────────────────────────┐
   │ write   discovery.fetch(url) → writer.write(origin)                  │
   │         WriterTransientError → retry with backoff (3 attempts)       │
   │         WriterContentBlockedError / other error → skip the candidate │
   │ render  renderer.render(story) → one RenderedPart per part           │
   │         any part fails → skip; nothing written (all or nothing)      │
   │ save    story_NN.mp4, story_NN_p2.mp4, … + a manifest per video      │
   │ publish (run only) hashtags once per story; part k in the slot after │
   │         part k-1; one log row per video (scheduled / failed);        │
   │         a failed part skips the rest of that story                   │
   └──────────────────────────────────────────────────────────────────────┘
```

The three entry points share those steps:

| Method | Does | Used by |
|---|---|---|
| `run(count, output_dir)` | find → write → render → save → schedule | bot daily job, `/autopost [n]`, `just daily-publish` |
| `generate(count, output_dir)` | find → write → render → save | `just daily-generate` (`publisher=None`) |
| `publish(videos)` | schedule manifests generated earlier | `just daily-publish-only DIR` |

`count` is a number of stories: a three-part story produces three videos in three
consecutive slots and counts once toward the target.

## Contracts

| Contract | Promise | Implementations |
|---|---|---|
| `StoryDiscovery` | ranked candidates, grades, and `fetch(url) → StoryOrigin` | `RedditStoryDiscovery` |
| `StoryWriter` | `write(origin) → Story`; errors classified as transient / content blocked / other | `ModelStoryWriter` (LLM), `StaticStoryWriter` (fixed stories) |
| `FootageSource` | `compile(min_duration) → Footage` at least that long, or `FootageShortfallError` | `YouTubeFootageSource`, `LocalFolderFootageSource` |
| `Renderer` | `render(story) → list[RenderedPart]`, one per part, raising if any part fails | `NarrationOverFootageRenderer` |
| `ITikTokPublisherProxy` | `publish_video(path, description, hashtags, schedule_at)` | `BrowserUseTikTokPublisherProxy` |
| `RunStore` | manifests, the publish log, and the post URLs already scheduled | `FileRunStore`; `InMemoryRunStore` in tests |

Discovery imports neither the video nor the speech stack, so the discovery scripts
start in a fraction of a second (`tests/capabilities/test_import_isolation.py`).

## Extending

### A rendering strategy

1. Write a class with a `name` and `async render(story, *, low_quality) -> list[RenderedPart]`
   in `src/capabilities/rendering/`. It may reuse `SpeechService`, `CaptionsService`,
   `CoverService`, `VideoComposer`, `TextCensor` and any `FootageSource`.
2. Register it in the `renderers` dict of `src/core/container.py`, keyed by its `name`.
3. Add the name to the `rendering_strategy` literal in
   `src/entities/configs/services/video.py`, then select it in `config.yaml`.

A name outside the literal is rejected when the config loads; a name missing from
the dict fails when the container builds the renderer, listing the registered
strategies. The flow does not change.

### A footage source

1. Implement `async compile(*, min_duration, low_quality) -> Footage` in
   `src/capabilities/footage/`, raising `FootageShortfallError(needed, got)` when it
   cannot cover the duration.
2. Add a branch to the `footage_source` `Selector` in `src/core/container.py` and the
   value to the `footage_source` literal in `VideoConfig`. Validate the settings it
   needs in `VideoConfig` (see `local_footage_dir`), so a bad config stops the bot at
   boot instead of at the first render.

Nothing in discovery, writing, storage or the flow changes.

### A store

Implement the four `RunStore` methods (`src/storage/contract.py`) and return it from
the `run_store` provider, or pass `store=` when building a `DailyRun`.
`tests/fakes/memory_store.py` is a complete example; the flow tests run the same
scenario against it and `FileRunStore` and expect identical results.

### A story writer or a new prompt

Prompts are plain Jinja2 files in `src/prompts/`: edit them without touching code.
The container calls `validate_all()` before building the LLM proxy, so a template
with broken syntax stops the process at start, naming the file. A different writer
(another model, hand-written stories) implements `StoryWriter` and replaces the
`story_writer` provider.

## Adapters

The bot and the CLI translate a command into one `DailyRun` call and forward its
progress lines; they hold no business rules.

- **Telegram bot** (`bots/satisfying_bot.py`, run by systemd with
  `python -m bots.satisfying_bot`): a daily job at `daily_hour_utc:daily_minute_utc`
  and `/autopost [n]` both call `container.daily_run(progress=send_to_chat).run(...)`
  under a `RunLock` (a second run is refused, not queued). Sending a Reddit URL
  renders it through `discovery.fetch → writer.write → renderer.render` and replies
  with the audio and the video.
- **CLI** (`scripts/daily_auto_publish.py`): `--count`, `--output-dir`,
  `--generate-only`, `--publish-only DIR`; progress goes to stdout.

`tests/flows/test_adapters.py` checks that both call the same method with the same
arguments.

## Wiring and Configuration

`ApplicationContainer` (`src/core/container.py`) builds everything from
`MainConfig`, read from the YAML file named by `CONFIG_PATH` (default
`config.yaml`). Proxies and capabilities are singletons; `daily_run`, `run_store` and
`tiktok_publisher` are factories, so each run gets a fresh publisher agent and
re-reads `TIKTOK_PUBLISH_LOG_PATH`.

Proxies follow one pattern: an interface in `proxies/interfaces.py`, one or more
implementations, and a factory in `proxies/factories.py` that picks one from the
config's `type`. To add a provider, add a config class with a new `type` literal to
the union, implement the interface, and add the branch to the factory.

`config.yaml` is a partial override: omitted keys keep the Pydantic default, and
keys the models no longer know are ignored. Secrets come from `.env`. See
[configuration.md](configuration.md).

## Tests

The suite runs without network or paid models (`uv run pytest`). The golden test
(`tests/flows/test_daily_run_golden.py`) drives the three modes through the real
container with fake proxies and compares messages, manifests, publish-log rows and
publisher calls with `tests/fixtures/daily_run_golden.json`, recorded before the
refactor. Rewrite the fixture only with `--update-golden` and review the diff: a
changed fixture means changed behaviour.
