from typing import List
from pydantic import BaseModel, Field


class History(BaseModel):
    title: str = Field("")
    content: str = Field("")
    speech_path: str = Field(None)