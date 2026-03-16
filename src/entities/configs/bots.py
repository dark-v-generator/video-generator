from typing import List
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class TelegramBotConfig(BaseYAMLModel):
    allowed_user_ids: List[int] = Field(default_factory=list)
    low_quality: bool = False


class BotsConfig(BaseYAMLModel):
    image_story_bot: TelegramBotConfig = Field(default_factory=TelegramBotConfig)
    two_part_history_bot: TelegramBotConfig = Field(default_factory=TelegramBotConfig)
