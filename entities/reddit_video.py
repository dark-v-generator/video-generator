from pydantic import BaseModel, Field
import yaml

from entities.captions import Captions
from entities.cover import RedditCover
from entities.history import History


class RedditHistory(BaseModel):
    cover: RedditCover = Field(RedditCover())
    captions: Captions = Field(Captions())
    history: History = Field(History())

    @staticmethod
    def from_yaml(file_path) -> "Captions":
        with open(file_path, "r") as file:
            data = yaml.safe_load(file)
            return Captions(**data)

    def save_yaml(self, output_path):
        with open(output_path, "w") as file:
            yaml.dump(self.model_dump(), file, allow_unicode=True, width=100, indent=4)
