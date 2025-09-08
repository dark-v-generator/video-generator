import random
from typing import List, Optional
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class CaptionsConfig(BaseYAMLModel):
    upper: bool = Field(True)
    font_file_id: Optional[str] = Field(None)
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
    watermark_file_id: Optional[str] = Field(
        None, title="File id of the water mark image"
    )
    end_silece_seconds: int = Field(3, title="End silence seconds")
    padding: int = Field(60, title="Padding")
    cover_duration: int = Field(5, title="Cover duration")
    width: int = Field(1080, title="Width of the video")
    height: int = Field(1920, title="Height of the video")
    youtube_channel_id: str = Field(
        "UCIXTGJvqvxWoWWstA66a2JQ", title="Youtube channel id"
    )
    ffmpeg_params: List[str] = Field([], title="ffmpeg params")


class LLMConfig(BaseYAMLModel):
    """Configuration for Large Language Model services"""

    provider: str = Field("openai", title="LLM provider (openai, local)")
    model: str = Field("gpt-5-mini-2025-08-07", title="Model to use")
    temperature: float = Field(0.7, title="Temperature for generation")
    max_tokens: int = Field(2000, title="Maximum tokens for generation")


class SpeechConfig(BaseYAMLModel):
    """Configuration for Text-to-Speech services"""

    provider: str = Field("fish-speech", title="Speech provider (coqui, fish-speech)")
    default_voice: str = Field("", title="Default voice to use")
    default_rate: float = Field(1.0, title="Default speech rate")


class MainConfig(BaseYAMLModel):
    @staticmethod
    def __generate_random_seed() -> str:
        return "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=10))

    video_config: VideoConfig = Field(VideoConfig(), title="Video configuration")
    cover_config: CoverConfig = Field(CoverConfig(), title="Cover configuration")
    captions_config: CaptionsConfig = Field(CaptionsConfig())
    llm_config: LLMConfig = Field(LLMConfig(), title="LLM configuration")
    speech_config: SpeechConfig = Field(SpeechConfig(), title="Speech configuration")
    seed: Optional[str] = Field(None, title="Seed")

    def int_seed(self) -> int:
        seed = self.seed or self.__generate_random_seed()
        return int.from_bytes(seed.encode(), "little")
