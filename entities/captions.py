import random
from typing import List
from pydantic import BaseModel, Field
from enum import Enum

import yaml
from entities.history import History


class CaptionSegment(BaseModel):
    start: float = Field(0)
    end: float = Field(0)
    text: str = Field('')

class Captions(BaseModel):
    segments: List[CaptionSegment] = Field([])

    @staticmethod
    def from_yaml(file_path) -> "Captions":
        with open(file_path, "r") as file:
            data = yaml.safe_load(file)
            return Captions(**data)

    def save_yaml(self, output_path):
        with open(output_path, "w") as file:
            yaml.dump(self.model_dump(), file, allow_unicode=True, width=100, indent=4)