from typing import List
from pydantic import BaseModel, Field


class History(BaseModel):
    title: str = Field("", title="Title of the history")
    # subtitle: str = Field("", title="Subtitle of the history")
    description: str = Field("", title="Description of the history")
    content: str = Field("", title="Content of the history")
    # hashtags: List[str] = Field("", title="List of hashtags")
    file_name: str = Field("", title="File name of the history")
    reddit_community: str = Field(None, title="Reddit community")
    reddit_post_author: str = Field(None, title="Reddit post author")
    reddit_community_url_photo: str = Field(None, title="Reddit community url photo")
