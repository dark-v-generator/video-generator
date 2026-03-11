from typing import List, Optional
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel

class VideoConfig(BaseYAMLModel):
    watermark_path: Optional[str] = Field(
        None, title="Path to the watermark image file"
    )
    end_silece_seconds: int = Field(3, title="End silence seconds")
    padding: int = Field(60, title="Padding")
    cover_duration: int = Field(5, title="Cover duration")
    width: int = Field(1080, title="Width of the video")
    height: int = Field(1920, title="Height of the video")
    youtube_channel_url: str = Field(
        "https://www.youtube.com/channel/UCIXTGJvqvxWoWWstA66a2JQ",
        title="Youtube channel url",
    )
    ffmpeg_params: List[str] = Field([], title="ffmpeg params")
