from typing import Literal, Union
from src.entities.base_yaml_model import BaseYAMLModel

class PyTubeYouTubeConfig(BaseYAMLModel):
    type: Literal["pytube"] = "pytube"

YouTubeConfigType = Union[PyTubeYouTubeConfig]
