from typing import Any, Dict


def build_nested_dict(data: Dict[str, Any]):
    config = {}
    for key, value in data.items():
        keys = key.split(".")
        sub_config = config
        for sub_key in keys[:-1]:
            if not sub_key in sub_config:
                sub_config[sub_key] = {}
            sub_config = sub_config[sub_key]
        sub_config[keys[-1]] = value
    return config