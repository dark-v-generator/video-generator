import time
import requests
from typing import List
from .interfaces import IImageGeneratorProxy
from src.entities.config.image_generation import LeonardoImageGenerationConfig


class LeonardoImageProxy(IImageGeneratorProxy):
    def __init__(self, config: LeonardoImageGenerationConfig):
        self.api_key = config.api_key
        if not self.api_key:
            raise ValueError("Leonardo API key is not set")

        self.base_url = "https://cloud.leonardo.ai/api/rest/v1"
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
    ) -> List[bytes]:

        # 1. Create generation job
        payload = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "num_images": num_images,
        }
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt

        response = requests.post(
            f"{self.base_url}/generations", json=payload, headers=self.headers
        )
        response.raise_for_status()

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
