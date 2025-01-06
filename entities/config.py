from pydantic import BaseModel, Field

class VideoConfig(BaseModel):
    watermark_path: str = Field(None, title="Path to the water mark image")
    background_audio_path: str = Field(None, title="Path to the background audio file")
    cover_path: str = Field(None, title="Path to the cover image")
    end_silece_seconds: int = Field(3, title="End silence seconds")
    padding: int = Field(50, title="Padding")
    cover_duration: int = Field(5, title="Cover duration")
    width: int = Field(720, title="Width of the video")
    height: int = Field(1280, title="Height of the video")


class MainConfig(BaseModel):
    output_path: str = Field(None, title="Path to save the output video")
    history_prompt: str = Field(None, title="Prompt for the history section")
    video_config: VideoConfig = Field(VideoConfig(), title="Video configuration")


