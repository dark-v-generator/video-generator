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
        title="Preprocessor ID for image reference (397=Phoenix CharRef, 133=SDXL CharRef, 233=Flux ContentRef, None=disabled)",
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


class LeonardoV2ImageGenerationConfig(BaseYAMLModel):
    type: Literal["leonardo-v2"] = "leonardo-v2"
    api_key: Optional[str] = Field(None, title="Leonardo API Key")
    model: str = Field("nano-banana-2", title="Model identifier string (e.g. nano-banana-2)")
    style_ids: list[str] = Field(default_factory=list, title="Style UUIDs")
    prompt_enhance: str = Field("OFF", title="ON or OFF")


class MidjourneyImageGenerationConfig(BaseYAMLModel):
    type: Literal["midjourney"] = "midjourney"
    api_key: Optional[str] = Field(None, title="Legnext API Key")
    prompt_suffix: str = Field(
        "--v 7 --ar 9:16",
        title="Appended to every prompt (version, aspect ratio, etc.)",
    )


class MockImageGenerationConfig(BaseYAMLModel):
    type: Literal["mock"] = "mock"


ImageGenerationConfigType = Union[
    LeonardoImageGenerationConfig,
    LeonardoV2ImageGenerationConfig,
    MidjourneyImageGenerationConfig,
    LocalImageGenerationConfig,
    RunPodImageGenerationConfig,
    MockImageGenerationConfig,
]
