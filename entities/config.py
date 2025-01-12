import random
from pydantic import BaseModel, Field
from enum import Enum
from entities.history import History


class HistorySource(Enum):
    REDDIT = "reddit"
    CHAT_GPT = "chat_gpt"
    CONFIG = "config"


class HistoryConfig(BaseModel):
    source: HistorySource = Field(HistorySource.CONFIG, title="Source of the history")
    prompt: str = Field(None, title="Prompt for auto generation")
    reddit_url: str = Field(None, title="Reddit URL")
    history: History = Field(History(), title="History fields")


class CoverConfig(BaseModel):
    subtitle: str = Field(None, title="Subtitle")
    title_font_family: str = Field("Arial", title="Font family")
    subtitle_font_family: str = Field("Arial", title="Subtitle font family")
    title_font_size: int = Field(80, title="Title font size")
    subtitle_font_size: int = Field(50, title="Subtitle font size")
    title_font_color: str = Field("#000000", title="Font color")
    subtitle_font_color: str = Field("#808080", title="Subtitle font color")
    background_color: str = Field("#FFFFFF", title="Background color")
    rounding_radius: int = Field(30, title="Rounding radius")
    padding: int = Field(50, title="Padding")


class VideoConfig(BaseModel):
    watermark_path: str = Field(None, title="Path to the water mark image")
    background_audio_path: str = Field(None, title="Path to the background audio file")
    end_silece_seconds: int = Field(3, title="End silence seconds")
    padding: int = Field(50, title="Padding")
    cover_duration: int = Field(5, title="Cover duration")
    width: int = Field(720, title="Width of the video")
    height: int = Field(1280, title="Height of the video")
    youtube_channel_id: str = Field(
        "UCCZIevhN62jJ2gb-u__M95g", title="Youtube channel id"
    )
    low_quality: bool = Field(False, title="Low quality")


class MainConfig(BaseModel):
    @staticmethod
    def __generate_random_seed() -> str:
        return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=10))

    output_path: str = Field(None, title="Path to save the output video")
    video_config: VideoConfig = Field(VideoConfig(), title="Video configuration")
    cover_config: CoverConfig = Field(CoverConfig(), title="Cover configuration")
    history_config: HistoryConfig = Field(
        HistoryConfig(), title="History configuration"
    )
    seed: str = Field(__generate_random_seed(), title="Seed")

    def int_seed(self) -> int:
        return int.from_bytes(self.seed.encode(), "little")
