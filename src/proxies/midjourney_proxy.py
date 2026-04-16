import logging
import time
from typing import List

import requests

from src.entities.configs.proxies.image_generation import MidjourneyImageGenerationConfig

from .interfaces import IImageGeneratorProxy

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 5
MAX_POLL_ATTEMPTS = 120


class MidjourneyImageProxy(IImageGeneratorProxy):
    """Midjourney image generation via the Legnext API."""

    BASE_URL = "https://api.legnext.ai/api/v1"

    def __init__(self, config: MidjourneyImageGenerationConfig):
        self.api_key = config.api_key
        if not self.api_key:
            raise ValueError("Legnext API key is not set")
        self.prompt_suffix = config.prompt_suffix
        self.headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
        character_references: dict[str, bytes] | None = None,
    ) -> List[bytes]:
        full_prompt = f"{prompt} {self.prompt_suffix}".strip()

        logger.info("Midjourney: submitting generation")
        response = requests.post(
            f"{self.BASE_URL}/diffusion",
            headers=self.headers,
            json={"text": full_prompt},
        )

        if response.status_code != 200:
            raise Exception(
                f"Legnext diffusion failed ({response.status_code}): {response.text}"
            )

        data = response.json()
        job_id = data.get("job_id")
        if not job_id:
            raise Exception(f"No job_id in Legnext response: {data}")

        logger.info("Midjourney: job %s submitted", job_id)

        image_urls = self._poll_until_complete(job_id)

        results: List[bytes] = []
        for url in image_urls[:num_images]:
            img_resp = requests.get(url, timeout=60)
            img_resp.raise_for_status()
            results.append(img_resp.content)

        return results

    def _poll_until_complete(self, job_id: str) -> list[str]:
        for attempt in range(MAX_POLL_ATTEMPTS):
            time.sleep(POLL_INTERVAL_SECONDS)
            resp = requests.get(
                f"{self.BASE_URL}/job/{job_id}",
                headers=self.headers,
            )
            resp.raise_for_status()
            data = resp.json()
            status = data.get("status")

            logger.info(
                "Midjourney: %s — status %s (poll %d)",
                job_id, status, attempt + 1,
            )

            if status == "completed":
                output = data.get("output", {})
                urls = output.get("image_urls") or []
                if not urls and output.get("image_url"):
                    urls = [output["image_url"]]
                if not urls:
                    raise Exception(
                        f"Midjourney job {job_id} completed but no image URLs in output"
                    )
                return urls

            if status == "failed":
                error = data.get("error", {})
                msg = error.get("message") or error.get("raw_message") or data
                raise Exception(f"Midjourney job {job_id} failed: {msg}")

        raise Exception(
            f"Timeout waiting for Midjourney job {job_id} "
            f"after {MAX_POLL_ATTEMPTS * POLL_INTERVAL_SECONDS}s"
        )
