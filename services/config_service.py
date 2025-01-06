import yaml

from entities.config import MainConfig

def get_main_config() -> MainConfig:
    with open('config.yaml', 'r') as file:
        data = yaml.safe_load(file)
        return MainConfig(**data['main'])