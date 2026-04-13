from typing import Literal, Optional, Union

from pydantic import Field

from src.entities.base_yaml_model import BaseYAMLModel


class ComfyUIVideoGenerationConfig(BaseYAMLModel):
    type: Literal["comfyui"] = "comfyui"
    base_url: str = Field("http://127.0.0.1:8188", title="ComfyUI base URL")
    poll_interval_seconds: int = Field(5, title="Seconds between status polls")
    max_poll_attempts: int = Field(360, title="Max polling attempts before timeout")
    image_node_id: str = Field("36", title="Workflow node ID for the LoadImage input")
    prompt_node_id: str = Field("30", title="Workflow node ID for the text prompt")
    width: int = Field(1360, title="Output video width")
    height: int = Field(768, title="Output video height")


VideoGenerationConfigType = Union[ComfyUIVideoGenerationConfig]
