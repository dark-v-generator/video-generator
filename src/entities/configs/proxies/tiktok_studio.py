from typing import Optional

from pydantic import Field

from src.entities.base_yaml_model import BaseYAMLModel


class TikTokStudioConfig(BaseYAMLModel):
    """How the performance collection reads the TikTok Studio.

    The reader opens the publisher's Chromium profile, so it never has its
    own login; ``user_data_dir`` only needs setting when that profile lives
    somewhere other than next to ``tiktok_publisher_config.cookies_path``.
    """

    user_data_dir: Optional[str] = Field(
        None,
        title="Chromium profile with the TikTok session "
        "(default: the publisher's <cookies stem>_userdata)",
    )
    headless: bool = Field(
        False,
        title="Run Chromium without a window. Headful is harder to detect.",
    )
    lookback_days: int = Field(
        30, title="How many days of posts a collection reads by default"
    )
    page_timeout_seconds: int = Field(
        60, title="How long to wait for a Studio page to load its data"
    )
    max_gap_hours: int = Field(
        12,
        title="Largest gap between the scheduled slot and TikTok's post time "
        "for a caption match to count",
    )
