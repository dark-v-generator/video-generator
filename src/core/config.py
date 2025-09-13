from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Settings(BaseSettings):
    # Collection names
    histories_collection_name: str = "histories"
    config_collection_name: str = "config"

    # File storage settings
    file_storage_base_path: str = ".storage"

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # External API settings
    openai_api_key: Optional[str] = None

    # LLM settings
    ollama_base_url: str = "http://localhost:11434"
    youtube_api_key: Optional[str] = None
    fish_audio_api_key: Optional[str] = None

    speech_provider: str = "fish-speech"
    llm_provider: str = "openai"
    llm_model: str = "gpt-5-mini-2025-08-07"

    # Video processing settings
    ffmpeg_path: Optional[str] = None

    # Environment
    environment: str = "development"
    debug: bool = True

    model_config = ConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
