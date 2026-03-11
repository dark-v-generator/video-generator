from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from typing import Optional


class Secrets(BaseSettings):
    # External API settings
    openai_api_key: Optional[str] = None
    youtube_api_key: Optional[str] = None
    elevenlabs_api_key: Optional[str] = None
    leonardo_api_key: Optional[str] = None

    # LLM settings
    ollama_base_url: str = "http://localhost:11434"

    model_config = ConfigDict(env_file=".env", case_sensitive=False, extra="ignore")


secrets = Secrets()
