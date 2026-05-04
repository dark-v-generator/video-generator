from typing import Dict
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class CensorshipConfig(BaseYAMLModel):
    extra_word_replacements: Dict[str, str] = Field(
        default_factory=dict,
        title="Additional word→replacement pairs to extend the default censorship mapping. "
        "Keys are matched case- and accent-insensitively; values are used verbatim.",
    )
