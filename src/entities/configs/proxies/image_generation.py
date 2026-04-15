from typing import Literal, Optional, Union
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class LeonardoElementConfig(BaseYAMLModel):
    ak_uuid: str = Field(..., title="Element akUUID")
    weight: float = Field(1.0, title="Element weight")


class LeonardoImageGenerationConfig(BaseYAMLModel):
    type: Literal["leonardo"] = "leonardo"
    api_key: Optional[str] = Field(None, title="Leonardo API Key")
    model_id: Optional[str] = Field(None, title="Leonardo Model ID (e.g. Phoenix)")
    style_uuid: Optional[str] = Field(
        None, title="Leonardo Style UUID (e.g. Cinematic)"
    )
    contrast: Optional[float] = Field(
        None, title="Contrast level (3=Low, 3.5=Medium, 4=High)"
    )
    elements: list[LeonardoElementConfig] = Field(
        default_factory=list, title="Leonardo Elements (LoRAs)"
    )
    character_ref_preprocessor_id: Optional[int] = Field(
        None,
        title="Preprocessor ID for Character Reference (397=Phoenix, 133=SDXL, None=disabled)",
    )
    character_ref_strength: str = Field(
        "Mid",
        title="Character Reference strength (Low, Mid, High)",
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
