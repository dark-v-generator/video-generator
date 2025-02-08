from typing import List
from pydantic import BaseModel, Field


class RedditPost(BaseModel):
    title: str = Field("", title="Title of the Reddit post")
    content: str = Field("", title="Content of the Reddit post")
    community: str = Field("", title="Community of the Reddit post")
    author: str = Field("", title="Author of the Reddit post")
    community_url_photo: str = Field("", title="URL of the community photo")
