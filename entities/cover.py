from pydantic import BaseModel, Field


class RedditCover(BaseModel):
    image_url: str = Field("")
    title: str = Field("", title="Content of the Reddit post")
    community: str = Field("", title="Community of the Reddit post")
    author: str = Field("", title="Author of the Reddit post")
