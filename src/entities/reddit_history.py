from datetime import datetime
import uuid
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel
from src.entities.cover import RedditCover
from src.entities.history import History


class RedditHistory(BaseYAMLModel):
    id: str = Field(str(uuid.uuid4()))
    cover: RedditCover = Field(RedditCover())
    history: History = Field(History())
    speech_path: str = Field("")
    regular_speech_path: str = Field("")
    captions_path: str = Field("")
    cover_path: str = Field("")
    folder_path: str = Field("")
    final_video_path: str = Field("")
    last_updated_at: datetime = Field(datetime.now())

    def save_yaml(self, output_path):
        self.last_updated_at = datetime.now()
        super().save_yaml(output_path)