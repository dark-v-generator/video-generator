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
EOF
```

## Run the Daily Pipeline

```bash
# Generate one video only (no publishing): output/daily/story_01.mp4 + story_01.json
just daily-generate 1

# Schedule what was generated
just daily-publish-only output/daily

# Full run: discover → generate → schedule
just daily-publish 3
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
