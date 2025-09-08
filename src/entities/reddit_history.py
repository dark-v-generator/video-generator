from datetime import datetime
import uuid
from typing import Optional
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel
from src.entities.cover import RedditCover
from src.entities.history import History
from src.entities.language import Language


class RedditHistory(BaseYAMLModel):
    id: str = Field()
    cover: RedditCover = Field(RedditCover())
    history: History = Field(History())
    speech_file_id: Optional[str] = Field(None)
    captions_file_id: Optional[str] = Field(None)
    cover_file_id: Optional[str] = Field(None)
    final_video_file_id: Optional[str] = Field(None)
    last_updated_at: datetime = Field(datetime.now())
    language: str = Field(Language.PORTUGUESE.value)

    def save_yaml(self, output_path):
        self.last_updated_at = datetime.now()
        super().save_yaml(output_path)

    def get_language(self) -> Language:
        if self.language:
            return Language(self.language)
        return Language.PORTUGUESE
