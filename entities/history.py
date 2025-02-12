from pydantic import BaseModel, Field
import unidecode


class History(BaseModel):
    title: str = Field("", title="Title of the history")
    content: str = Field("", title="Content of the history")
    gender: str = Field("male", title="History teller gender, can be male or female")

    def title_normalized(self) -> str:
        title = unidecode.unidecode(self.title)
        title = title.replace(" ", "_")
        title = title.lower()
        return title
