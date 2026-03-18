import io
import os
import tempfile
from typing import List
import torch
from diffusers import StableDiffusionPipeline
from PIL import Image
from .interfaces import IImageGeneratorProxy
from src.entities.configs.proxies.image_generation import LocalImageGenerationConfig

GENERATION_WIDTH = 512
GENERATION_HEIGHT = 768
NUM_INFERENCE_STEPS = 20


class LocalSDXLImageProxy(IImageGeneratorProxy):
    def __init__(self, config: LocalImageGenerationConfig):
        if torch.backends.mps.is_available():
            self.device = "mps"
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"

        # MPS float16 produces NaN in the VAE decoder → black images. Use float32.
        self.dtype = torch.float16 if self.device == "cuda" else torch.float32

        print(
            f"Loading {config.model_id} pipeline on {self.device} with {self.dtype}..."
        )
        self.pipeline = StableDiffusionPipeline.from_pretrained(
            config.model_id,
            torch_dtype=self.dtype,
            safety_checker=None,
        )
        self.pipeline.to(self.device)
        self.pipeline.enable_attention_slicing()
        print("Pipeline loaded successfully.")

        self._preview_dir = os.path.join(tempfile.gettempdir(), "video_gen_images")
        os.makedirs(self._preview_dir, exist_ok=True)
        self._image_counter = 0

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
    ) -> List[bytes]:

        print(
            f"Generating {num_images} image(s) at {GENERATION_WIDTH}x{GENERATION_HEIGHT} "
            f"(upscale to {width}x{height}) for prompt: '{prompt[:80]}...'"
        )

        prompts = [prompt] * num_images
        negative_prompts = [negative_prompt] * num_images if negative_prompt else None

        images = self.pipeline(
            prompt=prompts,
            negative_prompt=negative_prompts,
            num_inference_steps=NUM_INFERENCE_STEPS,
            guidance_scale=7.5,
            height=GENERATION_HEIGHT,
            width=GENERATION_WIDTH,
        ).images

        results = []
        for img in images:
            self._image_counter += 1
            preview_path = os.path.join(
                self._preview_dir, f"img_{self._image_counter:03d}.png"
            )
            img.save(preview_path, format="PNG")
            print(f"  Preview saved: {preview_path}")

            if (width, height) != (GENERATION_WIDTH, GENERATION_HEIGHT):
                img = img.resize((width, height), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            results.append(buf.getvalue())

        print("Generation complete.")
        return results
