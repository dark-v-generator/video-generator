from typing import Any, Dict
from werkzeug.datastructures import ImmutableMultiDict

class BaseFormRequest:
    def __init__(self, form: ImmutableMultiDict[str, str]):
        self.data: dict = BaseFormRequest.__build_nested_dict(form.to_dict())

    def __build_nested_dict(data: Dict[str, Any]) -> Dict[str, Any]:
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
    
    def get_bool(self, field_name: str, default_value: bool = False) -> bool:
        default = "on" if default_value else "off"
        return self.data.get(field_name, default) == "on"

    def get_float(self, field_name: str, default_value: float = 0.0) -> float:
        return float(self.data.get(field_name, str(default_value)))
    
    def get_str(self, field_name: str, default_value: str = "") -> str:
        return self.data.get(field_name, default_value)
    
    def get_int(self, field_name: str, default_value: int = 0) -> int:
        return int(self.data.get(field_name, str(default_value)))

class GenerateVideoRequest(BaseFormRequest):
    def __init__(self, form: ImmutableMultiDict[str, str]):
        super().__init__(form)
        self.low_quality = self.get_bool("low_quality")
        self.captions = self.get_bool("captions")
        self.speech = self.get_bool("speech")
        self.cover = self.get_bool("cover")
        self.rate = self.get_float("rate", default_value=1.5)
        self.enhance_captions = self.get_bool("enhance_captions", default_value=True)

class ScrapRedditPostRequest(BaseFormRequest):
    def __init__(self, form: ImmutableMultiDict[str, str]):
        super().__init__(form)
        self.enhance_history = self.get_bool("enhance_history")
        self.url = self.get_str("url")
        self.number_of_parts = self.get_int("number_of_parts", default_value=1)