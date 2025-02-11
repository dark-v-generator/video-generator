from typing import Any, Dict


def build_nested_dict(data: Dict[str, Any]):
    out_data = {}
    for key, value in data.items():
        keys = key.split(".")
        sub_data = out_data
        for sub_key in keys[:-1]:
            if not sub_key in sub_data:
                sub_data[sub_key] = {}
            sub_data = sub_data[sub_key]
        sub_data[keys[-1]] = value
    return out_data