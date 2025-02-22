import os

import yaml

from src.entities.language import Language


LANGUAGE_FILE = "config/language.yaml"


def __get_language_dict() -> dict:
    if not os.path.exists(LANGUAGE_FILE):
        return {}
    with open(LANGUAGE_FILE, "r") as file:
        data = yaml.safe_load(file)
        return data


def t(language: Language, key: str) -> str:
    dc = __get_language_dict()
    return dc.get(language.value, {}).get(key, "").strip()
