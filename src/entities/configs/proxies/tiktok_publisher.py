from pydantic import Field

from src.entities.base_yaml_model import BaseYAMLModel


class TikTokPublisherConfig(BaseYAMLModel):
    """Non-secret configuration for the TikTok auto-publisher agent.

    Secrets (email/password/API keys) still live in .env via Secrets;
    only knobs that are safe to commit live here.
    """

    agent_model: str = Field(
        "deepseek/deepseek-v4-flash",
        title="OpenRouter model id used by the publisher agent",
    )
    cookies_path: str = Field(
        ".storage/tiktok_cookies.json",
        title="Where to read/write the persisted TikTok session cookies",
    )
    headless: bool = Field(
        False,
        title="Run Chromium without a window. Headful is harder to detect.",
    )
    use_vision: bool = Field(
        False,
        title="Send screenshots to the LLM (required for image captchas)",
    )
    max_steps: int = Field(
        60,
        title="Maximum agent steps before giving up",
    )
