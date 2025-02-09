from typing import List
from pydantic import BaseModel, Field
import yaml


class BaseYAMLModel(BaseModel):
    @staticmethod
    def from_yaml(file_path) -> "BaseYAMLModel":
        with open(file_path, "r") as file:
            data = yaml.safe_load(file)
            return BaseYAMLModel(**data)

    def save_yaml(self, output_path):
        with open(output_path, "w") as file:
            yaml.dump(self.model_dump(), file, allow_unicode=True, width=100, indent=4)
