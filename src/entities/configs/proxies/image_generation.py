from typing import Literal, Union
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class LeonardoImageGenerationConfig(BaseYAMLModel):
    type: Literal["leonardo"] = "leonardo"
    api_key: str = Field(..., title="Leonardo API Key")


class LocalImageGenerationConfig(BaseYAMLModel):
    type: Literal["local"] = "local"
    model_id: str = Field("Lykon/dreamshaper-8", title="Local HuggingFace Model ID")


class MockImageGenerationConfig(BaseYAMLModel):
    type: Literal["mock"] = "mock"


ImageGenerationConfigType = Union[
    LeonardoImageGenerationConfig, LocalImageGenerationConfig, MockImageGenerationConfig
]
