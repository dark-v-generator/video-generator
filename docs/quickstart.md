# Quick Start

## Prerequisites

- Python 3.12+
- [just](https://github.com/casey/just) command runner
- [Ollama](https://ollama.ai/) running locally (default LLM provider)

## Setup

```bash
# 1. Install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Pull the default LLM model
ollama pull gemma3:12b

# 3. (Optional) Create .env for API keys
cat > .env << EOF
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
LEONARDO_API_KEY=...
EOF
```

## Generate a Reddit Video

```bash
# Fast preview (low quality, ~400px)
just generate-reddit-fast https://www.reddit.com/r/pettyrevenge/comments/...

# Full quality (1080×1920)
just generate-reddit https://www.reddit.com/r/pettyrevenge/comments/...
```

Output files are saved to `output/part1.mp4` and `output/part2.mp4`.

## CLI Options

```bash
python scripts/reddit_two_part_history.py <POST_URL> \
  --output-dir output \
  --language pt \           # pt, en, es, fr, de, it, ja, ko, zh
  --gender female \         # male, female (auto-detected if omitted)
  --rate 1.2 \              # TTS speech rate
  --low-quality             # fast preview rendering
```

## Switching Providers

Edit `config.yaml` to change providers. See [Configuration Guide](configuration.md) for all options.

**Example: Switch to OpenAI for LLM + transcription:**
```yaml
proxies:
  llm_config:
    type: dspy
    provider_config:
      provider: openai
      model: gpt-4o-mini
  transcription_config:
    type: openai
```

**Example: Switch to ElevenLabs for speech:**
```yaml
proxies:
  speech_config:
    type: elevenlabs
```

Don't forget to add the corresponding API key to `.env`.
