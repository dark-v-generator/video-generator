# Architecture Overview

## Project Structure

```
src/
├── core/                    # Application wiring
│   ├── container.py         # Dependency injection (DI) container
│   ├── secrets.py           # Environment-based API keys
│   └── logging_config.py    # Logging setup
├── entities/                # Data models
│   ├── config.py            # MainConfig (ProxiesConfig + ServicesConfig)
│   ├── configs/
│   │   ├── proxies/         # Config models for each proxy type
│   │   └── services/        # Config models for services (video, captions)
│   └── editor/              # MoviePy wrapper clips (VideoClip, AudioClip, etc.)
├── proxies/                 # External integrations
│   ├── interfaces.py        # Abstract proxy interfaces
│   ├── factories.py         # Factory classes that instantiate proxies from config
│   └── ...                  # Concrete proxy implementations
├── services/                # Business logic
│   ├── video_service.py     # Video composition
│   ├── captions_service.py  # Caption generation
│   ├── cover_service.py     # Cover image generation
│   ├── speech_service.py    # Text-to-speech
│   └── reddit_video_service.py  # Full Reddit → video pipeline
scripts/
│   └── reddit_two_part_history.py  # CLI script for two-part Reddit videos
config.yaml                  # Configuration overrides
.env                         # API keys and secrets
Justfile                     # Task runner
```

## Design Principles

### Dependency Injection

All dependencies are wired through `ApplicationContainer` (`src/core/container.py`). Services and proxies are instantiated as singletons and injected automatically.

### Proxy Pattern

External integrations follow the **proxy pattern**:
- Each integration type has an **interface** (e.g., `ILLMProxy`, `ISpeechProxy`) in `proxies/interfaces.py`
- Each interface has one or more **implementations** (e.g., `DSPyLLMProxy`, `PromptLLMProxy`)
- A **factory** in `proxies/factories.py` selects the right implementation based on the `type` field in `config.yaml`

To add a new provider:
1. Create a new config class with a unique `type` literal
2. Add it to the `Union` type alias
3. Implement the interface
4. Add a branch in the corresponding factory

### Configuration System

Configuration uses **Pydantic models with defaults**. `config.yaml` is a partial override file — any omitted field falls back to the Pydantic default. Secrets are loaded separately from `.env` via `pydantic-settings`.

## Pipeline Flow (Reddit Two-Part Video)

```
Reddit URL
    │
    ▼
┌─────────────┐    ┌───────────┐    ┌──────────────┐
│ RedditProxy │───▶│ LLMProxy  │───▶│ SpeechService│
│ (scrape)    │    │ (story +  │    │ (TTS audio)  │
│             │    │  gender)  │    │              │
└─────────────┘    └───────────┘    └──────┬───────┘
                                          │
    ┌─────────────────────────────────────┘
    │
    ▼
┌────────────────┐    ┌──────────────┐    ┌──────────────┐
│CaptionsService │    │ CoverService │    │ VideoService  │
│(transcribe +   │    │(Reddit cover │    │(compose final │
│ enhance)       │    │ image)       │    │ video)        │
└───────┬────────┘    └──────┬───────┘    └──────┬───────┘
        │                    │                    │
        └────────────────────┴────────────────────┘
                             │
                             ▼
                      output/part1.mp4
                      output/part2.mp4
```
