from typing import Type, TypeVar
from pydantic import BaseModel
import yaml

T = TypeVar("T", bound="BaseYAMLModel")


class BaseYAMLModel(BaseModel):
    @classmethod
    def from_yaml(cls: Type[T], file_path: str) -> T:
        with open(file_path, "r") as file:
            data = yaml.safe_load(file)
            return cls(**data)

    def save_yaml(self, output_path):
        with open(output_path, "w") as file:
            yaml.dump(self.model_dump(), file, allow_unicode=True, width=100, indent=4)
