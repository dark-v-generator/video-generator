from typing import Literal, Union, Optional
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class LocalTranscriptionConfig(BaseYAMLModel):
    type: Literal["local"] = "local"
    model: str = Field("base", title="Local Whisper Model Size")


class OpenAITranscriptionConfig(BaseYAMLModel):
    type: Literal["openai"] = "openai"
    model: str = Field("whisper-1", title="OpenAI Whisper Model")
    api_key: Optional[str] = Field(None, title="OpenAI API Key (or env var)")


TranscriptionConfigType = Union[LocalTranscriptionConfig, OpenAITranscriptionConfig]
