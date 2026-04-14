from typing import Annotated, Literal, Union

from pydantic import Discriminator, Tag

from src.entities.base_yaml_model import BaseYAMLModel


class BS4RedditConfig(BaseYAMLModel):
    type: Literal["bs4"] = "bs4"


class JsonRedditConfig(BaseYAMLModel):
    type: Literal["json"] = "json"


RedditConfigType = Annotated[
    Union[
        Annotated[BS4RedditConfig, Tag("bs4")],
        Annotated[JsonRedditConfig, Tag("json")],
    ],
    Discriminator("type"),
]
