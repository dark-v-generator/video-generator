from typing import Optional
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel

class CaptionsConfig(BaseYAMLModel):
    upper: bool = Field(True)
    font_path: str = Field("default_font.ttf", title="Path to the font file")
    font_size: int = Field(110)
    color: str = Field("#FFFFFF")
    stroke_color: str = Field("#000000")
    stroke_width: int = Field(8)
    upper_text: bool = Field(False)
    marging: int = Field(50)
    fade_duration: float = Field(0)
