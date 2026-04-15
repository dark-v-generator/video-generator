import logging
import time
import requests
from typing import List
from .interfaces import IImageGeneratorProxy
from src.entities.configs.proxies.image_generation import LeonardoImageGenerationConfig

logger = logging.getLogger(__name__)

PHOENIX_CHARACTER_REF_PREPROCESSOR_ID = 397
SDXL_CHARACTER_REF_PREPROCESSOR_ID = 133


class LeonardoImageProxy(IImageGeneratorProxy):
    def __init__(self, config: LeonardoImageGenerationConfig):
        self.api_key = config.api_key
        if not self.api_key:
            raise ValueError("Leonardo API key is not set")

        self.model_id = config.model_id
        self.style_uuid = config.style_uuid
        self.contrast = config.contrast
        self.elements = config.elements
        self.character_ref_preprocessor_id = config.character_ref_preprocessor_id
        self.character_ref_strength = config.character_ref_strength
        self.base_url = "https://cloud.leonardo.ai/api/rest/v1"
        self.headers = {
            "accept": "application/json",
            "authorization": f"Bearer {self.api_key}",
            "content-type": "application/json",
        }
        self._uploaded_image_cache: dict[int, str] = {}

    LEONARDO_MAX_DIMENSION = 1536
    LEONARDO_MAX_PROMPT_LENGTH = 1500

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
        character_references: dict[str, bytes] | None = None,
    ) -> List[bytes]:
        gen_w, gen_h = self._clamp_dimensions(width, height)
        prompt = self._truncate_prompt(prompt)

        payload: dict = {
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

        if character_references and self.character_ref_preprocessor_id:
            controlnets = self._build_character_controlnets(character_references)
            if controlnets:
                payload["controlnets"] = controlnets

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

        results = []
        for url in image_urls:
            img_resp = requests.get(url)
            img_resp.raise_for_status()
            results.append(img_resp.content)

        return results

    # ------------------------------------------------------------------
    # Character Reference helpers
    # ------------------------------------------------------------------

    def _build_character_controlnets(
        self, character_references: dict[str, bytes]
    ) -> list[dict]:
        # Leonardo Phoenix only supports ONE Character Reference per generation.
        # Use the first character in the dict (scene-level ordering puts the
        # most relevant character first).
        name, image_bytes = next(iter(character_references.items()))
        init_image_id = self._upload_init_image(name, image_bytes)
        if not init_image_id:
            return []

        if len(character_references) > 1:
            skipped = list(character_references.keys())[1:]
            logger.info(
                "Leonardo supports 1 character ref per image; using '%s', "
                "skipping %s",
                name,
                skipped,
            )

        return [
            {
                "initImageId": init_image_id,
                "initImageType": "UPLOADED",
                "preprocessorId": self.character_ref_preprocessor_id,
                "strengthType": self.character_ref_strength,
            }
        ]

    def _upload_init_image(self, name: str, image_bytes: bytes) -> str | None:
        cache_key = id(image_bytes)
        if cache_key in self._uploaded_image_cache:
            logger.info("Using cached upload for character '%s'", name)
            return self._uploaded_image_cache[cache_key]

        logger.info("Uploading reference image for character '%s'...", name)

        resp = requests.post(
            f"{self.base_url}/init-image",
            json={"extension": "png"},
            headers=self.headers,
        )
        if resp.status_code != 200:
            logger.error(
                "Failed to get presigned URL (%d): %s", resp.status_code, resp.text
            )
            return None

        upload_data = resp.json().get("uploadInitImage", {})
        init_image_id = upload_data.get("id")
        presigned_url = upload_data.get("url")
        fields = upload_data.get("fields")

        if not all([init_image_id, presigned_url, fields]):
            logger.error("Incomplete upload response: %s", upload_data)
            return None

        if isinstance(fields, str):
            import json

            fields = json.loads(fields)

        upload_resp = requests.post(
            presigned_url,
            data=fields,
            files={"file": ("character.png", image_bytes, "image/png")},
        )
        if upload_resp.status_code not in (200, 204):
            logger.error(
                "S3 upload failed (%d): %s",
                upload_resp.status_code,
                upload_resp.text[:200],
            )
            return None

        logger.info(
            "Uploaded character '%s' as init image %s", name, init_image_id
        )
        self._uploaded_image_cache[cache_key] = init_image_id
        return init_image_id

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

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
