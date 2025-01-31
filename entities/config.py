import random
from typing import List
from pydantic import BaseModel, Field
from enum import Enum
from entities.history import History


class HistorySource(Enum):
    REDDIT = "reddit"
    CONFIG = "config"

class CaptionsConfig(BaseModel):
    enabled: bool = Field(False)

class HistoryConfig(BaseModel):
    source: HistorySource = Field(HistorySource.CONFIG, title="Source of the history")
    prompt: str = Field(None, title="Prompt for auto generation")
    reddit_url: str = Field(None, title="Reddit URL")
    histories: List[History] = Field(None, title="Histories fields")
    number_of_parts: int = Field(1, title="Number of parts")


class CoverConfig(BaseModel):
    subtitle: str = Field(None, title="Subtitle")
    title_font_family: str = Field("Arial", title="Font family")
    subtitle_font_family: str = Field("Arial", title="Subtitle font family")
    title_font_size: int = Field(110, title="Title font size")
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
    padding: int = Field(60, title="Padding")
    cover_duration: int = Field(5, title="Cover duration")
    width: int = Field(1080, title="Width of the video")
    height: int = Field(1920, title="Height of the video")
    youtube_channel_id: str = Field(
        "UCIXTGJvqvxWoWWstA66a2JQ", title="Youtube channel id"
    )
    low_quality: bool = Field(False, title="Low quality")
    audio_preview: bool = Field(False, title="If true will render only the audio")


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
    captions_config: CaptionsConfig = Field(CaptionsConfig())
    seed: str = Field(__generate_random_seed(), title="Seed")

    def int_seed(self) -> int:
        return int.from_bytes(self.seed.encode(), "little")
