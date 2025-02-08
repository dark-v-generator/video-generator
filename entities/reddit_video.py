from typing import List
from pydantic import BaseModel, Field

from entities.captions import Captions
from entities.cover import RedditCover
from entities.history import History


class RedditVideo(BaseModel):
    cover: RedditCover = Field(RedditCover())
    captions: Captions = Field(Captions())
    history: History = Field(History())
    