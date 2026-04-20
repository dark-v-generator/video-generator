import logging
import time
from typing import List

import requests

from src.entities.configs.proxies.image_generation import LeonardoV2ImageGenerationConfig

from .interfaces import IImageGeneratorProxy

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 3
MAX_POLL_ATTEMPTS = 200

VALID_DIMENSION_PAIRS = [
    (1024, 1024),
    (848, 1264), (1264, 848),
    (896, 1200), (1200, 896),
    (928, 1152), (1152, 928),
    (768, 1376), (1376, 768),
]


class LeonardoV2ImageProxy(IImageGeneratorProxy):
    """Leonardo v2 API proxy (Nano Banana 2 and similar models)."""

    V2_BASE = "https://cloud.leonardo.ai/api/rest/v2"
    V1_BASE = "https://cloud.leonardo.ai/api/rest/v1"

    MAX_PROMPT_LENGTH = 1500

    def __init__(self, config: LeonardoV2ImageGenerationConfig):
        self.api_key = config.api_key
        if not self.api_key:
            raise ValueError("Leonardo API key is not set")
        self.model = config.model
        self.style_ids = config.style_ids
        self.prompt_enhance = config.prompt_enhance
        self.headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
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
        prompt = self._truncate_prompt(prompt)
        gen_w, gen_h = self._snap_dimensions(width, height)

        parameters: dict = {
            "width": gen_w,
            "height": gen_h,
            "prompt": prompt,
            "quantity": num_images,
            "prompt_enhance": self.prompt_enhance,
        }
        if self.style_ids:
            parameters["style_ids"] = self.style_ids

        payload: dict = {
            "model": self.model,
            "parameters": parameters,
            "public": False,
        }

        logger.info(
            "Leonardo v2: submitting %s generation (%dx%d -> %dx%d)",
            self.model, width, height, gen_w, gen_h,
        )
        response = requests.post(
            f"{self.V2_BASE}/generations", json=payload, headers=self.headers
        )

        data = response.json()

        if isinstance(data, list):
            msg = data[0].get("message", data) if data else data
            raise Exception(f"Leonardo v2 generation failed: {msg}")
        if response.status_code != 200:
            raise Exception(
                f"Leonardo v2 generation failed ({response.status_code}): {response.text}"
            )

        generation_id = data.get("generate", {}).get("generationId")
        if not generation_id:
            raise Exception(f"No generationId in Leonardo v2 response: {data}")

        logger.info("Leonardo v2: generation %s submitted", generation_id)

        image_urls = self._poll_until_complete(generation_id)

        results = []
        for url in image_urls:
            img_resp = requests.get(url)
            img_resp.raise_for_status()
            results.append(img_resp.content)

        return results

    def _poll_until_complete(self, generation_id: str) -> list[str]:
        for attempt in range(MAX_POLL_ATTEMPTS):
            time.sleep(POLL_INTERVAL_SECONDS)
            poll_resp = requests.get(
                f"{self.V1_BASE}/generations/{generation_id}",
                headers=self.headers,
            )
            poll_resp.raise_for_status()

            gen_data = poll_resp.json().get("generations_by_pk", {})
            status = gen_data.get("status")

            logger.info(
                "Leonardo v2: %s — status %s (poll %d)",
                generation_id,
                status,
                attempt + 1,
            )

            if status == "COMPLETE":
                return [
                    img["url"] for img in gen_data.get("generated_images", [])
                ]
            elif status == "FAILED":
                raise Exception(
                    f"Leonardo v2 generation {generation_id} failed"
                )

        raise Exception(
            f"Timeout waiting for Leonardo v2 generation {generation_id}"
        )

    @staticmethod
    def _snap_dimensions(width: int, height: int) -> tuple[int, int]:
        """Find the closest valid dimension pair by aspect ratio."""
        target_ratio = width / max(height, 1)
        best = min(
            VALID_DIMENSION_PAIRS,
            key=lambda pair: abs(pair[0] / pair[1] - target_ratio),
        )
        return best

    def _truncate_prompt(self, prompt: str) -> str:
        if len(prompt) <= self.MAX_PROMPT_LENGTH:
            return prompt
        return prompt[: self.MAX_PROMPT_LENGTH - 3] + "..."
