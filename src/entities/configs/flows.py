"""Settings the daily run reads, gathered from where they live in config.yaml."""

from dataclasses import dataclass

from ..config import MainConfig
from ..language import Language


@dataclass(frozen=True)
class DailyRunConfig:
    count: int
    publish_slots_local: list[str]
    publish_min_lead_minutes: int
    publish_hashtags: list[str]
    low_quality: bool
    language: Language
    story_retry_max: int = 3
    story_retry_base_delay: int = 5

    @classmethod
    def from_main_config(cls, config: MainConfig) -> "DailyRunConfig":
        bot = config.bots.satisfying_bot
        return cls(
            count=bot.daily_auto_publish_count,
            publish_slots_local=list(bot.publish_slots_local),
            publish_min_lead_minutes=bot.publish_min_lead_minutes,
            publish_hashtags=list(bot.publish_hashtags),
            low_quality=bot.low_quality,
            language=config.language,
        )
