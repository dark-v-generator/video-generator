import base64
import logging
import random
import time

import requests

from src.entities.configs.proxies.image_generation import RunPodImageGenerationConfig

from .interfaces import IImageGeneratorProxy

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
MAX_POLL_ATTEMPTS = 360 # The job can take a lot of time on cold start


class RunPodComfyUIProxy(IImageGeneratorProxy):
    def __init__(self, config: RunPodImageGenerationConfig):
        self.api_key = config.api_key
        if not self.api_key:
            raise ValueError("RunPod API key is not set")

        self.endpoint_id = config.endpoint_id
        self.base_url = f"https://api.runpod.ai/v2/{self.endpoint_id}"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
    ) -> list[bytes]:
        results: list[bytes] = []
        for _ in range(num_images):
            workflow = self._build_workflow(
                prompt, negative_prompt or "", width, height
            )
            job_id = self._submit_job(workflow)
            output = self._poll_until_complete(job_id)
            results.extend(self._extract_images(output))
        return results

    def _build_workflow(
        self, prompt: str, negative_prompt: str, width: int, height: int
    ) -> dict:
        return {
            "3": {
                "inputs": {
                    "seed": random.randint(0, 2**32 - 1),
                    "steps": 20,
                    "cfg": 1,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
                "class_type": "KSampler",
            },
            "4": {
                "inputs": {"ckpt_name": "flux1-dev-fp8.safetensors"},
                "class_type": "CheckpointLoaderSimple",
            },
            "5": {
                "inputs": {
                    "width": width,
                    "height": height,
                    "batch_size": 1,
                },
                "class_type": "EmptyLatentImage",
            },
            "6": {
                "inputs": {"text": prompt, "clip": ["4", 1]},
                "class_type": "CLIPTextEncode",
            },
            "7": {
                "inputs": {"text": negative_prompt, "clip": ["4", 1]},
                "class_type": "CLIPTextEncode",
            },
            "8": {
                "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
                "class_type": "VAEDecode",
            },
            "9": {
                "inputs": {
                    "filename_prefix": "RunPod_FLUX",
                    "images": ["8", 0],
                },
                "class_type": "SaveImage",
            },
        }

    def _submit_job(self, workflow: dict) -> str:
        payload = {"input": {"workflow": workflow}}
        response = requests.post(
            f"{self.base_url}/run", headers=self.headers, json=payload
        )
        if response.status_code != 200:
            raise Exception(
                f"RunPod job submission failed ({response.status_code}): {response.text}"
            )
        data = response.json()
        job_id = data.get("id")
        if not job_id:
            raise Exception(f"RunPod returned no job id: {data}")
        logger.info("RunPod job submitted: %s", job_id)
        return job_id

    def _poll_until_complete(self, job_id: str) -> dict:
        for attempt in range(MAX_POLL_ATTEMPTS):
            time.sleep(POLL_INTERVAL_SECONDS)
            response = requests.get(
                f"{self.base_url}/status/{job_id}", headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            status = data.get("status")
            logger.info(
                "RunPod job %s — status: %s (poll %d)", job_id, status, attempt + 1
            )

            if status == "COMPLETED":
                return data.get("output", {})
            elif status in ("FAILED", "CANCELLED", "TIMED_OUT"):
                raise Exception(f"RunPod job {job_id} ended with status: {status}")

        raise Exception(
            f"Timeout waiting for RunPod job {job_id} after {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s"
        )

    def _extract_images(self, output) -> list[bytes]:
        """Handle both common RunPod ComfyUI output formats."""
        images: list[bytes] = []

        if isinstance(output, dict):
            raw_images = output.get("images", [])
        elif isinstance(output, list):
            raw_images = output
        else:
            raise Exception(f"Unexpected RunPod output format: {type(output)}")

        for item in raw_images:
            if isinstance(item, dict):
                b64 = item.get("image") or item.get("data") or item.get("base64") or ""
            elif isinstance(item, str):
                b64 = item
            else:
                continue
            if b64:
                images.append(base64.b64decode(b64))

        if not images:
            item_summaries = []
            for item in raw_images:
                if isinstance(item, dict):
                    summary = {k: type(v).__name__ for k, v in item.items()}
                else:
                    summary = type(item).__name__
                item_summaries.append(summary)
            raise Exception(
                f"No images decoded from RunPod output. "
                f"items({len(raw_images)}): {item_summaries}"
            )

        logger.info(
            "Extracted %d image(s), sizes: %s", len(images), [len(i) for i in images]
        )
        return images
