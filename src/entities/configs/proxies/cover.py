from typing import Union
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class PlaywrightCoverConfig(BaseYAMLModel):
    """Playwright configuration for Cover Generation"""
    
    title_font_size: int = Field(150, title="Title font size")


CoverConfigType = Union[PlaywrightCoverConfig]
