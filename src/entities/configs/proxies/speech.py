from typing import Literal, Union, Optional, Dict
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel
from src.entities.language import Language


class SpeechVoiceConfig(BaseYAMLModel):
    male_voice_id: str
    female_voice_id: str


class EdgeTTSSpeechConfig(BaseYAMLModel):
    type: Literal["edge-tts"] = "edge-tts"
    voices: Dict[Language, SpeechVoiceConfig] = Field(default_factory=dict)


class ElevenLabsSpeechConfig(BaseYAMLModel):
    type: Literal["elevenlabs"] = "elevenlabs"
    voices: Dict[Language, SpeechVoiceConfig] = Field(default_factory=dict)
    api_key: Optional[str] = Field(None, title="Eleven Labs API Key")


SpeechConfigType = Union[EdgeTTSSpeechConfig, ElevenLabsSpeechConfig]
