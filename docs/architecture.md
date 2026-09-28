# Architecture Overview

The application does one thing every day: find Reddit stories, write a narration
script for each, render it as a vertical video and schedule it on TikTok. That
**daily run** is the main business flow. A second one, the **performance
collection**, runs when the operator asks: it reads how the published videos did
on TikTok and Reddit and attaches the numbers to each video's record. Everything
else is a piece they combine:

- a **story model** (`Story` with one or more parts) at the centre;
- six **capabilities**, each behind a contract: discovery, writing, footage,
  rendering, publishing and performance;
- a **storage boundary** for what survives between runs: the manifests and the
  publish log (`RunStore`), and the performance history (`HistoryStore`);
- two **adapters**, the Telegram bot and the command line, that start a flow and
  show its progress.

Dependencies point inwards: adapters → flow → capabilities → proxies, and every
layer may use the entities. The flows import contracts only; the container is the
one place that picks implementations.

```
 bots/satisfying_bot.py   scripts/daily_auto_publish.py            adapters
                          scripts/collect_performance.py
            │                          │
            └────────────┬─────────────┘
                         ▼
   src/flows/daily_run.py     src/flows/collect_performance.py     business flows
                         │
   ┌─────────┬───────┬───┴─────┬───────────┬────────────┬─────────────┐
   ▼         ▼       ▼         ▼           ▼            ▼             ▼
discovery writing rendering publishing performance  src/storage     capabilities
   │         │       │ └▶ footage          │         (RunStore,      + storage
   │         │       │         │           │          HistoryStore)
   ▼         ▼       ▼         ▼           ▼
             src/proxies/  (Reddit, LLM, TTS, Whisper,               I/O edges
             Playwright, YouTube, TikTok agent, TikTok Studio)
```

`scripts/performance_report.py` reads the history alone: it opens the SQLite
file directly, without the container, so it runs on the laptop without keys.

## Project Structure

```
src/
├── core/
│   ├── container.py          # Dependency injection: builds every piece from config.yaml
│   ├── paths.py              # HISTORY_DB_PATH, readable without importing the container
│   ├── recipe.py             # build_production_recipe: prompt versions, models, voice
│   ├── secrets.py            # API keys and tokens from .env
│   └── logging_config.py
├── entities/                 # Plain data, no I/O
│   ├── story.py              # StoryOrigin, StoryPart, Story (N parts), part_label
│   ├── rendered.py           # RenderedPart: video, audio, captions and cover of one part
│   ├── generated_video.py    # GeneratedVideo: what a manifest records
│   ├── history.py            # VideoRecord, ModelGrade, ProductionRecipe, PublishAttempt,
│   │                         # RedditSnapshot, PerformanceSnapshot, RunSummary, Collection,
│   │                         # CrossedRow + CROSSED_COLUMNS
│   ├── reddit_post.py, story_candidate.py, captions.py, cover.py,
│   │   language.py, speech_voice.py, transcription.py
│   ├── config.py             # MainConfig = proxies + services + bots + evaluation + language
│   ├── configs/
│   │   ├── proxies/          # One config model per proxy type
│   │   ├── services/         # video (footage_source, rendering_strategy, ...), captions, censorship
│   │   ├── bots.py           # bots.satisfying_bot: schedule, count, slots, hashtags
│   │   └── flows.py          # DailyRunConfig (bots.satisfying_bot + language),
│   │                         # CollectionConfig (tiktok_studio_config)
│   └── editor/               # MoviePy wrappers (VideoClip, AudioClip, CaptionsClip, ImageClip)
├── prompts/                  # Editable prompt templates, validated when the container starts
│   ├── story.jinja2, evaluate_story.jinja2, generate_hashtags.jinja2,
│   │   enhance_transcription.jinja2
│   ├── examples/             # Few-shot examples (transcription correction)
│   └── loader.py             # render(name, **vars), load_examples(name), validate_all()
├── proxies/                  # External integrations
│   ├── interfaces.py         # IRedditProxy, ILLMProxy, ISpeechProxy, ITranscriptionProxy,
│   │                         # IYouTubeProxy, ICoverProxy, ITikTokPublisherProxy,
│   │                         # ITikTokStudioProxy
│   ├── factories.py          # Picks the implementation from the config's `type`
│   ├── tiktok_studio_proxy.py  # Reads the Studio's own JSON with the publisher's profile
│   ├── tiktok_browser.py     # Profile, user agent and flags the publisher and Studio share
│   └── ...                   # json/bs4 Reddit, prompt/dspy/mock LLM, edge-tts, ElevenLabs,
│                             # local/OpenAI Whisper, Playwright cover, pytube + cache, TikTok agent
├── capabilities/
│   ├── discovery/            # StoryDiscovery → RedditStoryDiscovery
│   ├── writing/              # StoryWriter → ModelStoryWriter, StaticStoryWriter
│   ├── footage/              # FootageSource → YouTubeFootageSource, LocalFolderFootageSource
│   ├── rendering/            # Renderer → NarrationOverFootageRenderer (+ speech, captions,
│   │                         # cover, compose, censor, cta, registry)
│   ├── publishing/           # HashtagSuggester; the contract is ITikTokPublisherProxy
│   └── performance/          # PerformanceSource → StudioPerformanceSource; match() by caption
│                             # and slot
├── storage/
│   ├── contract.py           # RunStore, PublishLogEntry
│   ├── files.py              # FileRunStore: output/daily/*.json + .storage/tiktok_publish_log.csv
│   ├── history_contract.py   # HistoryStore, HistoryError, UnknownColumnError
│   └── sqlite_history.py     # SqliteHistoryStore: .storage/history.sqlite
└── flows/
    ├── daily_run.py          # DailyRun: generate, publish, run
    ├── run_record.py         # RunRecord: what a run tells the history, and its counts
    ├── collect_performance.py  # PerformanceCollection: collect, assign
    ├── publish_slots.py      # next_publish_slot, compute_publish_slots
    └── progress.py           # Progress callback type, RunLock, short_error
bots/
├── base.py                   # Telegram helpers (allowed users, sending audio and video)
└── satisfying_bot.py         # Telegram adapter: daily job, /autopost, /collect, URL → video
scripts/
├── daily_auto_publish.py     # CLI adapter: full run, --generate-only, --publish-only DIR
├── collect_performance.py    # CLI adapter: collection, --lookback-days N, --assign ID RECORD
├── performance_report.py     # The crossed view: table, --sort, --filter, --csv
├── import_history.py         # Publish log + manifests from before the history, once
├── tiktok_studio_probe.py    # Dumps what the Studio fetches (to pin its endpoints)
├── render_story.py           # A hand-written story JSON + a folder of clips → output/render/
├── find_best_stories.py, evaluate_story.py, list_posts.py   # Discovery diagnostics
└── publish_tiktok.py, tiktok_repl.py, ...                    # TikTok publisher tooling
tests/
├── fakes/                    # Fake proxies, publisher, footage, composer, InMemoryRunStore,
│                             # InMemoryHistoryStore, FakePerformanceSource
├── fixtures/                 # daily_run_golden.json, tiktok_studio_probe.json (redacted),
│                             # publish_log_sample.csv
├── flows/                    # Golden test, DailyRun (+ history), collection, adapters, slots,
│                             # module shape
├── capabilities/             # One file per capability (+ import isolation of discovery)
├── scripts/                  # import_history, performance_report
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

Each mode also writes to the history (`HistoryStore`), through `RunRecord`
(`src/flows/run_record.py`): a `RunSummary` per run (mode, requested, target,
candidates, produced, scheduled, skips by reason, why it stopped early), a
`VideoRecord` per video right after its manifest (the post's upvotes at
discovery, the model's grade, the production recipe, duration and voice), and a
`PublishAttempt` next to every publish-log row. Only results are kept, never the
model's reasoning or prompts. The history is the product, so a write that fails
stops the run; the manifest and the log row are already on disk by then.

## The Performance Collection

`PerformanceCollection` (`src/flows/collect_performance.py`) runs on demand,
from `/collect [days]` or `just prod-collect-performance [days]`, some days
after the videos went out and again to follow them.

```
 source.fetch(since)                    the account's videos (TikTok Studio)
 history.published_records(since)      records with an attempt for a slot since then,
                                        plus every record that knows its TikTok id
 match(records, videos, max_gap)        1. a record's stored tiktok_video_id
                                        2. same caption (hashtags, accents, quotes and
                                           punctuation folded), one candidate
                                        3. several candidates: the one whose slot is
                                           within max_gap_hours of TikTok's post time
                                        otherwise, or two videos for one record:
                                        unmatched or ambiguous (never guessed)
 source.metrics(id) per matched video   views, likes, comments, shares, saves,
                                        average watch, share watched to the end
 source.close()                         frees the Chromium profile before Reddit
 discovery.signals(post_url) per post   the post's upvotes now; gone → available=False
 history.record_collection(...)         one transaction: the collection row, the
                                        snapshots and each record's tiktok_video_id
```

Anything that fails before the last step (expired session, a Studio that changed
shape, Reddit down) stops the collection with the cause and writes nothing.
Every collection adds dated snapshots; earlier ones are never changed. A video
left unmatched or ambiguous is listed with its caption, date and id, and the
operator settles it with `--assign TIKTOK_ID RECORD_ID`; later collections then
match it by id.

The Studio reader opens the publisher's Chromium profile. The bot runs
`/autopost`, the daily job and `/collect` under one `RunLock`; the command line
does not see that lock, so a collection must not be started from it while a
publish is running.

## The History and the Crossed View

`SqliteHistoryStore` keeps everything in one file, `.storage/history.sqlite` on
the server (`HISTORY_DB_PATH`), one transaction per write:

| Table | One row per |
|---|---|
| `video_records` | rendered video: post, grade, recipe (flattened), hashtags, `tiktok_video_id` |
| `reddit_snapshots` | reading of the post: at discovery, and at each collection |
| `publish_attempts` | call to the publisher, the same facts as its publish-log row |
| `performance_snapshots` | matched video per collection |
| `collections` | collection: when, look-back, matched / unmatched / ambiguous |
| `run_summaries` | daily run, finished or not (`finished_at` empty = it died midway) |

Videos from before the history were imported once from the publish log and the
manifests (`scripts/import_history.py`): they are `imported`, with no grade, no
recipe and no discovery numbers.

`HistoryStore.crossed_view(since, filters, sort)` gives one `CrossedRow` per
record: the record, its discovery snapshot, the newest Reddit snapshot a
collection took, the newest TikTok numbers and the last attempt, whether or not
the video was ever collected. `CrossedRow.columns()` flattens it into
`CROSSED_COLUMNS`, the names sorting, filtering and the CSV use; a name outside
them raises `UnknownColumnError` before it reaches SQL. Empty values sort last in
both directions. The server's file is copied to the laptop with
`just sync-history` (server → laptop only) and read there with `just report`.

## Contracts

| Contract | Promise | Implementations |
|---|---|---|
| `StoryDiscovery` | ranked candidates, grades, and `fetch(url) → StoryOrigin` | `RedditStoryDiscovery` |
| `StoryWriter` | `write(origin) → Story`; errors classified as transient / content blocked / other | `ModelStoryWriter` (LLM), `StaticStoryWriter` (fixed stories) |
| `FootageSource` | `compile(min_duration) → Footage` at least that long, or `FootageShortfallError` | `YouTubeFootageSource`, `LocalFolderFootageSource` |
| `Renderer` | `render(story) → list[RenderedPart]`, one per part, raising if any part fails | `NarrationOverFootageRenderer` |
| `ITikTokPublisherProxy` | `publish_video(path, description, hashtags, schedule_at)` | `BrowserUseTikTokPublisherProxy` |
| `RunStore` | manifests, the publish log, and the post URLs already scheduled | `FileRunStore`; `InMemoryRunStore` in tests |
| `HistoryStore` | records, attempts, run summaries, collections and snapshots; every failed write raises; `crossed_view` | `SqliteHistoryStore`; `InMemoryHistoryStore` in tests |
| `PerformanceSource` | `fetch(since) → list[TikTokVideoStats]`, `metrics(video_id)`, `close()` | `StudioPerformanceSource`; `FakePerformanceSource` in tests |
| `ITikTokStudioProxy` | `list_videos(since)`, `video_analytics(id)`; `TikTokSessionExpiredError`, `TikTokStudioLayoutError` naming the missing field | `PatchrightTikTokStudioProxy` |

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

### A performance source

1. Implement `fetch(*, since)`, `metrics(video_id)` and `close()` of
   `PerformanceSource` (`src/capabilities/performance/contract.py`), for example
   over an analytics export or an official API. `fetch` returns `TikTokVideoStats`
   with the caption and post time the matching uses; a number the source does not
   have stays `None`.
2. Return it from the `performance_source` provider in `src/core/container.py`.

Matching, the history and the crossed view do not change.
`tests/fakes/performance.py` is a complete example.

### A story writer or a new prompt

Prompts are plain Jinja2 files in `src/prompts/`: edit them without touching code.
The container calls `validate_all()` before building the LLM proxy, so a template
with broken syntax stops the process at start, naming the file. A different writer
(another model, hand-written stories) implements `StoryWriter` and replaces the
`story_writer` provider.

## Adapters

The bot and the CLI translate a command into one flow call and forward its
progress lines; they hold no business rules.

- **Telegram bot** (`bots/satisfying_bot.py`, run by systemd with
  `python -m bots.satisfying_bot`): a daily job at `daily_hour_utc:daily_minute_utc`
  and `/autopost [n]` both call `container.daily_run(progress=send_to_chat).run(...)`
  under a `RunLock` (a second run is refused, not queued). Sending a Reddit URL
  renders it through `discovery.fetch → writer.write → renderer.render` and replies
  with the audio and the video.
  `/collect [days]` calls `container.performance_collection(progress=send_to_chat)
  .collect(...)` under the same lock.
- **CLI** (`scripts/daily_auto_publish.py`): `--count`, `--output-dir`,
  `--generate-only`, `--publish-only DIR`; progress goes to stdout.
  `scripts/collect_performance.py`: `--lookback-days N` or `--assign TIKTOK_ID
  RECORD_ID`.

`tests/flows/test_adapters.py` checks that both call the same method with the same
arguments.

## Wiring and Configuration

`ApplicationContainer` (`src/core/container.py`) builds everything from
`MainConfig`, read from the YAML file named by `CONFIG_PATH` (default
`config.yaml`). Proxies and capabilities are singletons; `daily_run`, `run_store`,
`history_store`, `tiktok_publisher`, `tiktok_studio_proxy` and
`performance_collection` are factories, so each run gets a fresh publisher agent
and Studio reader, its own SQLite connection, and re-reads
`TIKTOK_PUBLISH_LOG_PATH` and `HISTORY_DB_PATH`.

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
changed fixture means changed behaviour. The history did not change it: the
golden points `HISTORY_DB_PATH` at a temporary file.

The history tests run the same scenario against `SqliteHistoryStore` and
`InMemoryHistoryStore` and expect the same result. The Studio parser is tested
against `tests/fixtures/tiktok_studio_probe.json`, a redacted dump of what the
Studio returned on the server; no test opens a browser.
