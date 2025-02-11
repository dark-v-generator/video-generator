import uuid
from pydantic import Field
from entities.base_yaml_model import BaseYAMLModel
from entities.cover import RedditCover
from entities.history import History


class RedditHistory(BaseYAMLModel):
    id: str = Field(str(uuid.uuid4()))
    cover: RedditCover = Field(RedditCover())
    history: History = Field(History())
    speech_path: str = Field("")
    regular_speech_path: str = Field("")
    captions_path: str = Field("")
    cover_path: str = Field("")
    folder_path: str = Field("")