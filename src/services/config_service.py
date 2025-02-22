import os
from src.entities.config import MainConfig


def get_main_config(config_path: str = "config.yaml") -> MainConfig:
    if not os.path.isfile(config_path):
        MainConfig().save_yaml(config_path)
    return MainConfig.from_yaml(config_path)


def save_main_config(config_dict: dict, config_path: str = "config.yaml") -> MainConfig:
    MainConfig(**config_dict).save_yaml(config_path)
