from typing import List
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class PreparedStoriesConfig(BaseYAMLModel):
    """Where stories prepared on the laptop are sent and where the server reads them."""

    remote: str = Field(
        "gustavo@192.168.1.100:~/video-generator/.storage/prepared",
        title="SSH destination (user@host:dir) used by `prepare_story.py ship/queue`",
    )
    inbox_dir: str = Field(
        ".storage/prepared",
        title="Queue root on the server; holds inbox/, done/ and failed/",
    )
    fill_with_discovery: bool = Field(
        True,
        title="Complete the daily count with automatic discovery when the queue is short",
    )


class TelegramBotConfig(BaseYAMLModel):
    allowed_user_ids: List[int] = Field(default_factory=list)
    low_quality: bool = False
    daily_hour_utc: int = Field(17, title="Hour (UTC) to run daily /find")
    daily_minute_utc: int = Field(0, title="Minute (UTC) to run daily /find")

    daily_auto_publish_count: int = Field(
        4,
        title="Number of top stories to auto-generate and schedule daily",
    )
    publish_slots_local: List[str] = Field(
        default_factory=lambda: ["12:00", "18:00", "19:00", "20:00"],
        title="Local-time slots for scheduled TikTok posts (HH:MM)",
    )
    publish_min_lead_minutes: int = Field(
        30,
        title="Minimum minutes from now for a schedule slot to be eligible",
    )
    publish_hashtags: List[str] = Field(
        default_factory=list,
        title="Default hashtags appended to every auto-published video",
    )
    prepared_stories: PreparedStoriesConfig = Field(
        default_factory=PreparedStoriesConfig,
        title="Hand-off of locally prepared stories",
    )


class BotsConfig(BaseYAMLModel):
    image_story_bot: TelegramBotConfig = Field(default_factory=TelegramBotConfig)
    satisfying_bot: TelegramBotConfig = Field(default_factory=TelegramBotConfig)
