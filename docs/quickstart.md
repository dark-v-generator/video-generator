# Quick Start

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- [just](https://github.com/casey/just)
- ffmpeg on the PATH (Whisper decodes the narration with it)

## Setup

```bash
uv sync                                  # dependencies + test tools
uv run playwright install chromium       # renders the cover card
cp config.dev.yaml config.yaml           # mock LLM, edge-tts, local Whisper
```

Discovery lists subreddits through Reddit's OAuth API, so even the dev config needs
a Reddit app (type *script*, at reddit.com/prefs/apps):

```bash
cat > .env << EOF
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
EOF
```

With `config.dev.yaml` nothing else is paid or needs a key: the LLM is a mock, the
voice is edge-tts and Whisper runs locally. `config.prod.yaml` writes with
OpenRouter models and needs `OPENROUTER_API_KEY`.

```bash
uv run pytest                            # no network, no models
```

## Run the Daily Pipeline

```bash
# Find, write and render one story, without publishing:
# output/daily/story_01.mp4 + story_01.json
just daily-generate 1

# Schedule what was generated
just daily-publish-only output/daily

# Full run: find → write → render → schedule
just daily-publish 3
```

A story in several parts produces `story_NN.mp4`, `story_NN_p2.mp4`, … and one
manifest per video; `daily-publish` schedules the parts in consecutive slots.
Scheduling needs a TikTok session, which only exists on the production server (see
the README). The `prod-*` recipes run the same commands there.

## Render a Story by Hand

`render-story` turns a story you wrote into video over a folder of `.mp4` clips —
no Reddit, no LLM writing, no YouTube.

```bash
cat > /tmp/story.json << 'JSON'
{"title": "Minha sogra tentou me expulsar da minha própria casa",
 "parts": ["Ela entrou com a chave que eu nunca dei...", "No dia seguinte..."],
 "narrator_gender": "female", "language": "pt-br",
 "origin": {"url": "https://www.reddit.com/r/x/comments/abc/t/", "title": "t", "content": "c",
            "community": "r/x", "author": "u/y", "community_image_url": ""}}
JSON
just render-story /tmp/story.json path/to/clips   # output/render/part1.mp4, part2.mp4
```

Each part becomes its own video with ` - Parte N` on the cover.

## Switching Providers

Providers are chosen in `config.yaml`; see the [Configuration Guide](configuration.md)
for every option. For example, local backgrounds instead of YouTube:

```yaml
services:
  video_config:
    footage_source: local
    local_footage_dir: assets/backgrounds
```

or ElevenLabs for the narration (plus `ELEVENLABS_API_KEY` in `.env`):

```yaml
proxies:
  speech_config:
    type: elevenlabs
```
