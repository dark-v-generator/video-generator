import random
from typing import List, Optional
from pydantic import Field
from entities.base_yaml_model import BaseYAMLModel


class CaptionsConfig(BaseYAMLModel):
    upper: bool = Field(True)
    font_path: str = Field("assets/bangers.ttf")
    font_size: int = Field(110)
    color: str = Field("#FFFFFF")
    stroke_color: str = Field("#000000")
    stroke_width: int = Field(8)
    upper_text: bool = Field(False)
    marging: int = Field(50)
    fade_duration: float = Field(0)


class CoverConfig(BaseYAMLModel):
    title_font_size: int = Field(110, title="Title font size")


class VideoConfig(BaseYAMLModel):
    watermark_path: Optional[str] = Field(None, title="Path to the water mark image")
    end_silece_seconds: int = Field(3, title="End silence seconds")
    padding: int = Field(60, title="Padding")
    cover_duration: int = Field(5, title="Cover duration")
    width: int = Field(1080, title="Width of the video")
    height: int = Field(1920, title="Height of the video")
    youtube_channel_id: str = Field(
        "UCIXTGJvqvxWoWWstA66a2JQ", title="Youtube channel id"
    )
    low_quality: bool = Field(False, title="Low quality")
    low_resolution: bool = Field(False, title="Change resolution to low")
    ffmpeg_params: List[str] = Field([], title="ffmpeg params")


class MainConfig(BaseYAMLModel):
    @staticmethod
    def __generate_random_seed() -> str:
        return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=10))

    video_config: VideoConfig = Field(VideoConfig(), title="Video configuration")
    cover_config: CoverConfig = Field(CoverConfig(), title="Cover configuration")
    captions_config: CaptionsConfig = Field(CaptionsConfig())
    histories_path: str = Field("output", title="Path to save the output video")
    seed: str = Field(__generate_random_seed(), title="Seed")

    def int_seed(self) -> int:
        return int.from_bytes(self.seed.encode(), "little")
