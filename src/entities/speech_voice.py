from typing import Optional
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel
from src.entities.language import Language


class SpeechVoice(BaseYAMLModel):
    id: str = Field()
    name: Optional[str] = Field(None)
    image_url: Optional[str] = Field(None)
    language: Language = Field(Language.PORTUGUESE)
