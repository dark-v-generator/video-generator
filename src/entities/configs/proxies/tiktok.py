from typing import Literal, Union
from pydantic import Field
from src.entities.base_yaml_model import BaseYAMLModel


class TikTokUploaderConfig(BaseYAMLModel):
    type: Literal["tiktok-uploader"] = "tiktok-uploader"
    cookies_path: str = Field("config/tiktok_cookies.txt", title="Path to TikTok cookies file")
    headless: bool = Field(True, title="Run browser in headless mode")
    browser: str = Field("chrome", title="Browser to use for upload")


TikTokConfigType = Union[TikTokUploaderConfig]
