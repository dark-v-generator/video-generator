from pydantic import BaseModel, Field
from typing import Optional, List


class VideoConfigResponse(BaseModel):
    """Response model for video configuration"""

    watermark_path: Optional[str] = None
    end_silence_seconds: int = 3
    padding: int = 60
    cover_duration: int = 5
    width: int = 1080
    height: int = 1920
    youtube_channel_id: str = "UCIXTGJvqvxWoWWstA66a2JQ"
    low_quality: bool = False
    low_resolution: bool = False
    ffmpeg_params: List[str] = []


class CoverConfigResponse(BaseModel):
    """Response model for cover configuration"""

    title_font_size: int = 110


class CaptionsConfigResponse(BaseModel):
    """Response model for captions configuration"""

    upper: bool = True
    font_size: int = 110
    color: str = "#FFFFFF"
    stroke_color: str = "#000000"
    stroke_width: int = 8
    upper_text: bool = False
    margin: int = 50
    fade_duration: float = 0.0


class MainConfigResponse(BaseModel):
    """Response model for main configuration"""

    video_config: VideoConfigResponse
    cover_config: CoverConfigResponse
    captions_config: CaptionsConfigResponse
    seed: str


class ConfigUpdateRequest(BaseModel):
    """Request model for updating configuration"""

    video_config: Optional[dict] = None
    cover_config: Optional[dict] = None
    captions_config: Optional[dict] = None
    seed: Optional[str] = None
