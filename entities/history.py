from typing import List
from pydantic import BaseModel, Field


class History(BaseModel):
    title: str = Field("", title="Title of the history")
    # subtitle: str = Field("", title="Subtitle of the history")
    description: str = Field("", title="Description of the history")
    content: str = Field("", title="Content of the history")
    # hashtags: List[str] = Field("", title="List of hashtags")
    file_name: str = Field("unamed", title="File name of the history")
    reddit_community: str = Field(None, title="Reddit community")
    reddit_post_author: str = Field(None, title="Reddit post author")
    reddit_community_url_photo: str = Field(None, title="Reddit community url photo")


class MultiplePartHistory(BaseModel):
    title: str = Field("", title="Title of the history")
    parts: List[str] = Field([], title="List of parts of the history")
    file_name: str = Field("", title="File name of the history")
    reddit_community: str = Field(None, title="Reddit community")
    reddit_post_author: str = Field(None, title="Reddit post author")
    reddit_community_url_photo: str = Field(None, title="Reddit community url photo")

    def __get_part(self, index) -> History:
        title = self.title + f" - Parte {index + 1}"
        content = self.parts[index]
        if index != len(self.parts) -1:
             content += f"\nCurta e me siga para parte {index + 2}"
        file_name = self.file_name + f'_{index + 1}' 
        return History(
            title=title,
            content=content,
            file_name=file_name,
            reddit_community=self.reddit_community,
            reddit_post_author=self.reddit_post_author,
            reddit_community_url_photo=self.reddit_community_url_photo,
        )

    def get_histories(self) -> List[History]:
        n = len(self.parts)
        histories: List[History] = []
        for i in range(n):
            histories.append(self.__get_part(i))
        return histories
