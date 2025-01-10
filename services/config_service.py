import yaml
from entities.config import MainConfig


def get_main_config(config_path: str = "config.yaml") -> MainConfig:
    with open(config_path, "r") as file:
        data = yaml.safe_load(file)
        return MainConfig(**data["main"])
