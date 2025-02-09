from typing import List
from pydantic import BaseModel, Field


class History(BaseModel):
    title: str = Field("", title="Title of the history")
    content: str = Field("", title="Content of the history")
    gender: str = Field("male", title="History teller gender, can be male or female")