import copy
import json
import logging
import random
import time
from pathlib import Path
from typing import Any

import requests

from src.entities.configs.proxies.video_generation import ComfyUIVideoGenerationConfig

from .interfaces import IVideoGeneratorProxy

logger: logging.Logger = logging.getLogger(__name__)


class ComfyUIVideoProxy(IVideoGeneratorProxy):
    _WORKFLOW_PATH: Path = Path(__file__).parent / "workflows" / "cogvideox_i2v.json"

    _base_url: str
    _poll_interval: int
    _max_polls: int
    _image_node_id: str
    _prompt_node_id: str
    _default_width: int
    _default_height: int
    _base_workflow: dict[str, Any]

    def __init__(self, config: ComfyUIVideoGenerationConfig):
        self._base_url = config.base_url.rstrip("/")
        self._poll_interval = config.poll_interval_seconds
        self._max_polls = config.max_poll_attempts
        self._image_node_id = config.image_node_id
        self._prompt_node_id = config.prompt_node_id
        self._default_width = config.width
        self._default_height = config.height

        with open(self._WORKFLOW_PATH, "r", encoding="utf-8") as f:
            self._base_workflow = json.load(f)

    def generate_video(
        self,
        prompt: str,
        reference_image: bytes,
        width: int = 1360,
        height: int = 768,
    ) -> bytes:
        image_name: str = self._upload_image(reference_image)
        workflow: dict[str, Any] = self._build_workflow(prompt, image_name, width, height)
        prompt_id: str = self._queue_prompt(workflow)
        return self._poll_until_complete(prompt_id)

    def _upload_image(self, image_data: bytes) -> str:
        files: dict[str, tuple[str, bytes, str]] = {
            "image": ("input_frame.jpg", image_data, "image/jpeg"),
        }
        response: requests.Response = requests.post(
            f"{self._base_url}/upload/image", files=files
        )
        response.raise_for_status()
        name: str = response.json()["name"]
        logger.info("Uploaded reference image to ComfyUI as: %s", name)
        return name

    def _build_workflow(
        self, prompt: str, image_name: str, width: int, height: int
    ) -> dict[str, Any]:
        workflow: dict[str, Any] = copy.deepcopy(self._base_workflow)
        workflow[self._image_node_id]["inputs"]["image"] = image_name
        workflow[self._prompt_node_id]["inputs"]["prompt"] = prompt

        resize_node: dict[str, Any] | None = workflow.get("37")
        if resize_node:
            resize_node["inputs"]["width"] = width
            resize_node["inputs"]["height"] = height

        sampler_node: dict[str, Any] | None = workflow.get("63")
        if sampler_node:
            sampler_node["inputs"]["seed"] = random.randint(0, 2**32 - 1)

        return workflow

    def _queue_prompt(self, workflow: dict[str, Any]) -> str:
        payload: dict[str, Any] = {"prompt": workflow}
        response: requests.Response = requests.post(
            f"{self._base_url}/prompt", json=payload
        )
        response.raise_for_status()
        prompt_id: str = response.json()["prompt_id"]
        logger.info("ComfyUI job queued — prompt_id: %s", prompt_id)
        return prompt_id

    def _poll_until_complete(self, prompt_id: str) -> bytes:
        for attempt in range(1, self._max_polls + 1):
            time.sleep(self._poll_interval)

            response: requests.Response = requests.get(
                f"{self._base_url}/history/{prompt_id}"
            )
            response.raise_for_status()
            history: dict[str, Any] = response.json()

            if prompt_id not in history:
                logger.debug("Job %s not in history yet (poll %d)", prompt_id, attempt)
                continue

            job: dict[str, Any] = history[prompt_id]
            status_str: str = job.get("status", {}).get("status_str", "")

            if status_str == "error":
                messages: list[Any] = job.get("status", {}).get("messages", [])
                raise RuntimeError(
                    f"ComfyUI job {prompt_id} failed: {messages}"
                )

            outputs: dict[str, Any] = job.get("outputs", {})
            if not outputs:
                logger.debug("Job %s has no outputs yet (poll %d)", prompt_id, attempt)
                continue

            logger.info("ComfyUI job %s completed (poll %d)", prompt_id, attempt)
            return self._download_video(outputs)

        raise TimeoutError(
            f"ComfyUI job {prompt_id} did not finish after "
            f"{self._max_polls * self._poll_interval}s"
        )

    def _download_video(self, outputs: dict[str, Any]) -> bytes:
        for _node_id, node_output in outputs.items():
            gifs: list[dict[str, Any]] = node_output.get("gifs", [])
            if not gifs:
                continue

            video_info: dict[str, Any] = gifs[0]
            parameters: dict[str, str] = {
                "filename": video_info["filename"],
                "subfolder": video_info.get("subfolder", ""),
                "type": video_info.get("type", "output"),
            }
            response: requests.Response = requests.get(
                f"{self._base_url}/view", params=parameters
            )
            response.raise_for_status()
            logger.info(
                "Downloaded video %s (%d bytes)",
                video_info["filename"],
                len(response.content),
            )
            return response.content

        raise RuntimeError(
            f"No video output found in ComfyUI results. "
            f"Output node keys: {list(outputs.keys())}"
        )
