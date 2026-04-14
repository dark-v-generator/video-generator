import time
import requests
from typing import List
from .interfaces import IImageGeneratorProxy
from src.entities.configs.proxies.image_generation import LeonardoImageGenerationConfig


class LeonardoImageProxy(IImageGeneratorProxy):
    def __init__(self, config: LeonardoImageGenerationConfig):
        self.api_key = config.api_key
        if not self.api_key:
            raise ValueError("Leonardo API key is not set")

        self.model_id = config.model_id
        self.style_uuid = config.style_uuid
        self.contrast = config.contrast
        self.elements = config.elements
        self.base_url = "https://cloud.leonardo.ai/api/rest/v1"
        self.headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }

    LEONARDO_MAX_DIMENSION = 1536
    LEONARDO_MAX_PROMPT_LENGTH = 1500

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
    ) -> List[bytes]:
        gen_w, gen_h = self._clamp_dimensions(width, height)
        prompt = self._truncate_prompt(prompt)

        payload = {
            "prompt": prompt,
            "width": gen_w,
            "height": gen_h,
            "num_images": num_images,
        }
        if self.model_id:
            payload["modelId"] = self.model_id
        if self.style_uuid:
            payload["styleUUID"] = self.style_uuid
        if self.contrast is not None:
            payload["contrast"] = self.contrast
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if self.elements:
            payload["elements"] = [
                {"akUUID": e.ak_uuid, "weight": e.weight} for e in self.elements
            ]

        response = requests.post(
            f"{self.base_url}/generations", json=payload, headers=self.headers
        )
        if response.status_code != 200:
            raise Exception(
                f"Leonardo AI generation failed ({response.status_code}): {response.text}"
            )

        data = response.json()
        generation_id = data.get("sdGenerationJob", {}).get("generationId")
        if not generation_id:
            raise Exception(f"Failed to get generationId from Leonardo AI: {data}")

        # 2. Poll for completion
        max_retries = 30
        image_urls = []
        for _ in range(max_retries):
            time.sleep(2)
            poll_resp = requests.get(
                f"{self.base_url}/generations/{generation_id}", headers=self.headers
            )
            poll_resp.raise_for_status()

            gen_data = poll_resp.json().get("generations_by_pk", {})
            status = gen_data.get("status")

            if status == "COMPLETE":
                image_urls = [
                    img["url"] for img in gen_data.get("generated_images", [])
                ]
                break
            elif status == "FAILED":
                raise Exception("Leonardo AI generation failed.")

        else:
            raise Exception("Timeout waiting for Leonardo AI generation.")

        # 3. Download images
        results = []
        for url in image_urls:
            img_resp = requests.get(url)
            img_resp.raise_for_status()
            results.append(img_resp.content)

        return results

    def _truncate_prompt(self, prompt: str) -> str:
        limit = self.LEONARDO_MAX_PROMPT_LENGTH
        if len(prompt) <= limit:
            return prompt
        return prompt[: limit - 3] + "..."

    def _clamp_dimensions(self, width: int, height: int) -> tuple[int, int]:
        """Scale down dimensions proportionally if either exceeds Leonardo's limit."""
        max_dim = self.LEONARDO_MAX_DIMENSION
        if width <= max_dim and height <= max_dim:
            return width, height
        scale = min(max_dim / width, max_dim / height)
        return int(width * scale), int(height * scale)
