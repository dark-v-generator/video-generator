from typing import Literal, Optional, Union
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class LeonardoElementConfig(BaseYAMLModel):
    ak_uuid: str = Field(..., title="Element akUUID")
    weight: float = Field(1.0, title="Element weight")


class LeonardoImageGenerationConfig(BaseYAMLModel):
    type: Literal["leonardo"] = "leonardo"
    api_key: Optional[str] = Field(None, title="Leonardo API Key")
    model_id: Optional[str] = Field(None, title="Leonardo Model ID (e.g. Flux Dev)")
    style_uuid: Optional[str] = Field(
        None, title="Leonardo Style UUID (e.g. Cinematic)"
    )
    contrast: Optional[float] = Field(
        None, title="Contrast level (3=Low, 3.5=Medium, 4=High)"
    )
    elements: list[LeonardoElementConfig] = Field(
        default_factory=list, title="Leonardo Elements (LoRAs)"
    )


class LocalImageGenerationConfig(BaseYAMLModel):
    type: Literal["local"] = "local"
    model_id: str = Field("Lykon/dreamshaper-8", title="Local HuggingFace Model ID")


class RunPodImageGenerationConfig(BaseYAMLModel):
    type: Literal["runpod"] = "runpod"
    api_key: Optional[str] = Field(None, title="RunPod API Key")
    endpoint_id: str = Field("ipgjjtsxkkyogn", title="RunPod Serverless Endpoint ID")


class MockImageGenerationConfig(BaseYAMLModel):
    type: Literal["mock"] = "mock"


ImageGenerationConfigType = Union[
    LeonardoImageGenerationConfig,
    LocalImageGenerationConfig,
    RunPodImageGenerationConfig,
    MockImageGenerationConfig,
]
