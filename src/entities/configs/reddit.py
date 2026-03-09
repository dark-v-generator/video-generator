from typing import Literal, Union
from src.entities.base_yaml_model import BaseYAMLModel


class BS4RedditConfig(BaseYAMLModel):
    type: Literal["bs4"] = "bs4"


RedditConfigType = Union[BS4RedditConfig]
