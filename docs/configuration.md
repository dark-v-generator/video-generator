# Configuration Guide

Configuration has two layers:

1. **A YAML file** — providers, models, video layout, the daily run's schedule. The
   process reads the file named by `CONFIG_PATH` (default `config.yaml`). The repo
   ships `config.dev.yaml` (mock LLM, edge-tts, local Whisper) and
   `config.prod.yaml` (OpenRouter models) to copy from.
2. **`.env`** — API keys, tokens and credentials.

The YAML is a partial override: any key you omit keeps the Pydantic default, and
keys the models do not know (for example from features that were removed) are
ignored. The models live in `src/entities/config.py` and `src/entities/configs/`.

---

## Config Structure

```yaml
language: pt-br              # output language of scripts, voices and part labels

proxies:
  llm_config: { ... }
  history_adaptation_llm_config: { ... }   # optional
  speech_config: { ... }
  transcription_config: { ... }
  reddit_config: { ... }
  youtube_config: { ... }
  cover_config: { ... }
  tiktok_publisher_config: { ... }
  tiktok_studio_config: { ... }            # optional: the performance collection

services:
  video_config: { ... }
  captions_config: { ... }
  censorship_config: { ... }

bots:
  satisfying_bot: { ... }    # the daily run: schedule, count, slots, hashtags

evaluation: { ... }          # which subreddits discovery reads
```

---

## Proxies

### LLM (`llm_config`, `history_adaptation_llm_config`)

`llm_config` grades candidates, suggests hashtags and corrects the Whisper
transcription against the script. `history_adaptation_llm_config` writes the story
script; when it is omitted, `llm_config` writes it too.

```yaml
llm_config:
  type: prompt          # "prompt" | "dspy" | "mock"
  provider_config:
    provider: openrouter
    model: deepseek/deepseek-v4-flash
history_adaptation_llm_config:
  type: prompt
  provider_config:
    provider: openrouter
    model: moonshotai/kimi-k2.6
    reasoning_effort: high
    max_tokens: 12000
```

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | `prompt` / `dspy` / `mock` | `dspy` | `prompt` renders the Jinja2 templates of `src/prompts/` and calls the model through litellm; `dspy` uses DSPy signatures; `mock` returns canned text with no model (dev and tests) |
| `provider_config.provider` | `openrouter` / `openai` / `google` / `ollama` | `ollama` | Where the model runs |
| `provider_config.model` | `str` | `gemma3:12b` | Model id for that provider |
| `provider_config.temperature` | `float?` | provider default | Sampling temperature |
| `provider_config.max_tokens` | `int?` | provider default | Output token cap |
| `provider_config.reasoning_effort` | `none` … `high` | unset | OpenRouter only. Reasoning tokens are billed as output |

The prompts themselves are files in `src/prompts/` (`story.jinja2`,
`evaluate_story.jinja2`, `generate_hashtags.jinja2`, `enhance_transcription.jinja2`).
Edit them directly; a template with broken syntax stops the process at start and
names the file.

> **Secrets**: `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` or
> `OLLAMA_BASE_URL`, depending on the provider.

---

### Speech (`speech_config`)

Text-to-speech for the narration.

```yaml
speech_config:
  type: edge-tts
  default_rate: 1.5
  voices:            # optional per-language overrides (keys: pt, en, es, ...)
    pt:
      male_voice_id: "pt-BR-AntonioNeural"
      female_voice_id: "pt-BR-FranciscaNeural"
```

| Provider | `type` | API key | Notes |
|---|---|---|---|
| Edge TTS | `edge-tts` | No | Free Microsoft neural voices. `default_rate` (default `1.0`) multiplies every requested rate: `1.5` is edge-tts `+50%` |
| ElevenLabs | `elevenlabs` | `ELEVENLABS_API_KEY` | Premium voices |

The voice is picked by the story's narrator gender.

---

### Transcription (`transcription_config`)

Speech-to-text with word timestamps, used for the captions.

```yaml
transcription_config:
  type: local
  model: base
```

| Provider | `type` | API key | Notes |
|---|---|---|---|
| Local Whisper | `local` | No | Models `tiny`, `base`, `small`, `medium`, `large` |
| OpenAI Whisper | `openai` | `OPENAI_API_KEY` | Model `whisper-1` |

---

### Reddit (`reddit_config`)

How discovery lists subreddits and reads posts.

```yaml
reddit_config:
  type: json
```

| `type` | Default | Notes |
|---|---|---|
| `json` | | Reddit's OAuth `.json` endpoints for listing and reading posts. All shipped configs use it |
| `bs4` | ✓ | Scrapes the post page to read a single post; listing subreddits still goes through the `.json` endpoints |

Either way the daily run lists subreddits over OAuth, so it needs `REDDIT_CLIENT_ID`
and `REDDIT_CLIENT_SECRET` (an app of type *script* at reddit.com/prefs/apps); a
missing pair fails naming both variables.

---

### Cover (`cover_config`)

The Reddit-style card shown at the start of the video, rendered with Playwright.

| Field | Type | Default | Description |
|---|---|---|---|
| `title_font_size` | `int` | `150` | Font size of the title on the card |

---

### YouTube (`youtube_config`)

YouTube video listing and downloading for background compilations.

```yaml
youtube_config:
  type: pytube
  download_clients: [WEB, MWEB, WEB_SAFARI]
  cache:
    enabled: true
    dir: ~/.cache/video-generator/backgrounds
    max_gigabytes: 20
```

Currently only `pytube` is available. No API key required for basic usage.
Downloads can optionally carry a proof-of-origin token to get past YouTube's bot
detection — it is a secret, so it lives in the `.env` rather than here; see
[po-token.md](./po-token.md).

| Field | Type | Default | Description |
|---|---|---|---|
| `type` | `"pytube"` | `"pytube"` | Backend used to list and download videos |
| `download_clients` | `list[str]` | `["WEB", "MWEB", "WEB_SAFARI"]` | InnerTube clients tried in order. pytubefix's own default (`ANDROID_VR`) is answered with a bot-detection error, so the client is always named explicitly; the extras are fallbacks for when one starts getting blocked |

#### Background cache (`youtube_config.cache`)

Downloaded clips are kept on disk and reused. The daily run draws from the same
pool of videos, so re-downloading them is both the slowest step and what gets
the machine's IP throttled (HTTP 429) — with a warm cache a repeated run makes
no download requests at all and completes even while YouTube is refusing them.

Omitting the whole `cache` block keeps the defaults below (the cache is on).

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | `bool` | `true` | `false` restores the previous behaviour: every run re-downloads every clip |
| `dir` | `str` | `~/.cache/video-generator/backgrounds` | Where the mp4 files live. `~` is expanded and the directory is created on demand; the default sits outside the working tree. Caches are per machine — nothing is shared between the laptop and the server |
| `max_gigabytes` | `float` | `20` | Disk budget for the directory (GiB). Must be greater than zero. After each download the least recently used clips are evicted until the directory fits again — serving a clip from the cache counts as using it, so the pool in daily rotation survives |

Entries are named `{video_id}-{hq|lq}.mp4`, so the two quality tracks are cached
independently and never serve each other. Caching is best-effort: an unreadable
or unwritable directory logs a warning and the run downloads as before, and a
truncated file is discarded and downloaded again rather than failing the run.
Download errors themselves — a 429 included — still abort immediately.

Eviction only ever touches `{video_id}-{hq|lq}.mp4` entries in that directory,
and never the clip the current run just downloaded — those bytes are already in
memory, so even a cap smaller than a single clip degrades to "nothing is cached"
rather than breaking the run.

---

### TikTok publisher (`tiktok_publisher_config`)

Non-secret settings of the browser agent that schedules the videos. The login
lives in `.env`; the session lives in the cookies and the Chromium profile.

| Field | Type | Default | Description |
|---|---|---|---|
| `agent_model` | `str` | `deepseek/deepseek-v4-flash` | OpenRouter model driving the agent |
| `cookies_path` | `str` | `.storage/tiktok_cookies.json` | Persisted session |
| `headless` | `bool` | `false` | Headful is harder to detect; the server runs it under Xvfb |
| `use_vision` | `bool` | `false` | Send screenshots to the model (needed for image captchas) |
| `use_thinking` | `bool` | `false` | Ask for the optional thinking field in the agent's replies |
| `max_steps` | `int` | `60` | Steps before the agent gives up |
| `capture_raw_llm_failures` | `bool` | `true` | Keep the provider's raw reply when parsing fails |
| `raw_llm_body_max_chars` | `int` | `65536` | Size cap of that raw reply |

> **Secrets**: `TIKTOK_EMAIL`, `TIKTOK_PASSWORD`, `OPENROUTER_API_KEY`.

---

### TikTok Studio (`tiktok_studio_config`)

How the performance collection (`just prod-collect-performance`, `/collect`) reads
the account's numbers from the TikTok Studio. There is no model and no login of
its own: it opens the publisher's Chromium profile, with the session the
publisher already keeps. Every key is optional.

| Field | Type | Default | Description |
|---|---|---|---|
| `user_data_dir` | `str` | the publisher's profile | Chromium profile with the session; unset, it is `<cookies_path stem>_userdata` next to `tiktok_publisher_config.cookies_path` (`.storage/tiktok_cookies_userdata`) |
| `headless` | `bool` | `false` | Headful is harder to detect; the server runs it under Xvfb |
| `lookback_days` | `int` | `30` | Days of posts a collection reads when none is given (`/collect 60`, `just prod-collect-performance 60` override it) |
| `page_timeout_seconds` | `int` | `60` | How long to wait for a Studio page to load its data |
| `max_gap_hours` | `int` | `12` | Two records with the same caption: the one scheduled within this many hours of TikTok's post time is the match; otherwise the video is reported as ambiguous |

```yaml
proxies:
  tiktok_studio_config:
    lookback_days: 30
    max_gap_hours: 12
```

The collection and the publisher share that profile and must never run at the
same time. The bot serializes `/collect`, `/autopost` and the daily job; from the
command line, do not start a collection while a publish is running.

---

## Services

### Video (`video_config`)

Where the background comes from, how a story becomes video, and the layout of the
result.

```yaml
video_config:
  footage_source: youtube          # or "local"
  # local_footage_dir: assets/backgrounds
  rendering_strategy: narration-over-footage
  call_to_action_path: assets/call_to_action.png
  cover_duration: 3
  fps: 60
  youtube_channel_urls:
    - https://www.youtube.com/@FoodieBoyKR
    - https://www.youtube.com/@cookming
  youtube_surface: shorts
  youtube_channel_strategy: all
  youtube_pool_size: 100
  ffmpeg_params: ["-crf", "23", "-preset", "medium"]
```

#### Footage and rendering

| Field | Type | Default | Description |
|---|---|---|---|
| `footage_source` | `youtube` / `local` | `youtube` | `youtube` downloads clips from the channels below through the background cache. `local` concatenates the `.mp4` files of `local_footage_dir` and never touches the network |
| `local_footage_dir` | `str?` | `null` | Folder of `.mp4` clips. Required with `footage_source: local`: without it the config fails to load, naming the key. The clips are shuffled and joined until they cover the narration; when they cannot, the render fails saying how many seconds are missing |
| `rendering_strategy` | `narration-over-footage` | `narration-over-footage` | How a story becomes video. The only strategy narrates each part over the footage, with the cover, captions and call to action on top. See [architecture.md](architecture.md#a-rendering-strategy) to add one |

#### YouTube backgrounds

| Field | Type | Default | Description |
|---|---|---|---|
| `youtube_channel_urls` | `list[str]` | `[]` | Channels to draw clips from. When set, takes precedence over `youtube_channel_url` |
| `youtube_channel_url` | `str` | `https://www.youtube.com/@FoodieBoyKR` | Fallback channel |
| `youtube_channel_strategy` | `random` / `all` | `random` | One random channel per compilation, or candidates from every channel |
| `youtube_pool_size` | `int` | `50` | Newest videos considered per channel. `0` means all |
| `youtube_surface` | `videos` / `shorts` | `videos` | Which tab of the channel to list |
| `anti_fingerprint` | block | see below | Randomised transforms applied to every clip, local or YouTube |

`anti_fingerprint` fields: `enabled` (`true`), `mirror` (`true`), `zoom` (`1.04`),
`brightness_delta` (`0.02`), `contrast_delta` (`0`), `hue_shift_degrees` (`0`),
`speed_delta` (`0.02`). Each run samples new values inside those ranges, so two
outputs never share a perceptual hash.

#### Layout and encoding

| Field | Type | Default | Description |
|---|---|---|---|
| `width` / `height` | `int` | `1080` / `1920` | Output size, 9:16 |
| `fps` | `int` | `30` | Output frame rate; without it the render would inherit the background's (often 60) |
| `padding` | `int` | `60` | Horizontal padding of overlays |
| `cover_width_ratio` | `float` | `0.82` | Cover width as a fraction of the video width |
| `cover_duration` | `float` | `0.5` | Seconds the cover stays on screen. It overlays the start of the narration and does not lengthen the video |
| `call_to_action_path` | `str?` | `null` | Overlay image shown from the closing call to action onward |
| `watermark_path` | `str?` | `null` | Watermark image |
| `end_silece_seconds` | `int` | `3` | Silence appended after the narration |
| `ffmpeg_params` | `list[str]` | `[]` | Extra ffmpeg encoding parameters |

With `bots.satisfying_bot.low_quality: true`, width, height and padding are scaled
down to a 400 px tall preview and YouTube clips are downloaded at low resolution.

---

### Captions (`captions_config`)

| Field | Type | Default | Description |
|---|---|---|---|
| `font_path` | `str` | `default_font.ttf` | TTF font |
| `font_size` | `int` | `110` | Base size (scaled in low quality) |
| `color` / `stroke_color` | `str` | `#FFFFFF` / `#000000` | Text and outline colour |
| `stroke_width` | `int` | `8` | Outline thickness |
| `upper_text` | `bool` | `false` | Show the captions in uppercase |
| `marging` | `int` | `50` | Text margin in pixels |
| `fade_duration` | `float` | `0` | Fade per word, in seconds |
| `vertical_position` | `float` | `0.68` | Where captions start, as a fraction of the height (below the cover) |

---

### Censorship (`censorship_config`)

Captions and the cover title are censored before rendering, so audio-moderated
words do not appear on screen; the narration is not changed.

| Field | Type | Default | Description |
|---|---|---|---|
| `extra_word_replacements` | `dict[str, str]` | `{}` | Word → replacement pairs added to the built-in list. Keys match ignoring case and accents |

---

## Daily run (`bots.satisfying_bot`)

Read by the Telegram bot and by `scripts/daily_auto_publish.py`; both run the same
`DailyRun`.

| Field | Type | Default | Description |
|---|---|---|---|
| `allowed_user_ids` | `list[int]` | `[]` | Telegram users allowed to talk to the bot; the first one receives the daily run's messages |
| `daily_hour_utc` / `daily_minute_utc` | `int` | `17` / `0` | When the bot starts the daily run |
| `daily_auto_publish_count` | `int` | `4` | Stories per run. A story in several parts counts once and takes one slot per part |
| `publish_slots_local` | `list[str]` | `["12:00", "18:00", "19:00", "20:00"]` | Local-time TikTok slots (`HH:MM`) |
| `publish_min_lead_minutes` | `int` | `30` | Minimum lead time for a slot to be eligible |
| `publish_hashtags` | `list[str]` | `[]` | Hashtags added to every scheduled video |
| `low_quality` | `bool` | `false` | Render at preview resolution |

## Discovery (`evaluation`)

| Field | Type | Default | Description |
|---|---|---|---|
| `subreddits` | `list[str]` | 11 subreddits (see `src/entities/config.py`) | Where the daily run looks for stories |
| `min_chars` / `max_chars` | `int` | `500` / `15000` | Post length accepted as a candidate |

---

## Secrets (`.env`)

API keys and credentials live in a `.env` file at the project root (or in the
environment). All are optional; set the ones your providers need.

| Variable | Needed for |
|---|---|
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` | Discovery (listing subreddits) |
| `OPENROUTER_API_KEY` | LLM with `provider: openrouter`; the TikTok publisher agent |
| `OPENAI_API_KEY` | LLM with `provider: openai`; `transcription_config.type: openai` |
| `GOOGLE_API_KEY` | LLM with `provider: google` |
| `OLLAMA_BASE_URL` | LLM with `provider: ollama` (default `http://localhost:11434`) |
| `ELEVENLABS_API_KEY` | `speech_config.type: elevenlabs` |
| `TELEGRAM_SATISFYING_BOT_TOKEN` | The Telegram bot |
| `TIKTOK_EMAIL`, `TIKTOK_PASSWORD` | TikTok login (the publisher agent) |
| `YOUTUBE_PO_TOKEN`, `YOUTUBE_VISITOR_DATA` | Background downloads refused by YouTube's bot detection; set as a pair — see [po-token.md](./po-token.md) |

Three more environment variables change where things are read or written:

| Variable | Default | Effect |
|---|---|---|
| `CONFIG_PATH` | `config.yaml` | YAML file to load |
| `TIKTOK_PUBLISH_LOG_PATH` | `.storage/tiktok_publish_log.csv` | Publish log; its `scheduled` rows keep discovery from picking a post twice |
| `HISTORY_DB_PATH` | `.storage/history.sqlite` | Performance history (SQLite): what the daily run and the collection write, and what `just report` reads. Read at every run, so tests point it at a temporary file |
