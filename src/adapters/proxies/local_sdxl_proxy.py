import io
from typing import List
import torch
from diffusers import AutoPipelineForText2Image
from .interfaces import IImageGeneratorProxy
from src.entities.config.image_generation import LocalImageGenerationConfig


class LocalSDXLImageProxy(IImageGeneratorProxy):
    def __init__(self, config: LocalImageGenerationConfig):
        # Choose device: mps if Apple Silicon, else cuda, else cpu
        if torch.backends.mps.is_available():
            self.device = "mps"
        elif torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"

        # Use float16 on MPS/CUDA to save memory and speed up, float32 on CPU
        self.dtype = torch.float16 if self.device in ["mps", "cuda"] else torch.float32

        print(
            f"Loading {config.model_id} pipeline on {self.device} with {self.dtype}..."
        )
        self.pipeline = AutoPipelineForText2Image.from_pretrained(
            config.model_id,
            torch_dtype=self.dtype,
            variant="fp16" if self.dtype == torch.float16 else None,
        )
        self.pipeline.to(self.device)
        print("Pipeline loaded successfully.")

    def generate_image(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
    ) -> List[bytes]:

        print(
            f"Generating {num_images} image(s) of size {width}x{height} for prompt: '{prompt}'"
        )

        # Prepare inputs for batched generation
        prompts = [prompt] * num_images
        negative_prompts = [negative_prompt] * num_images if negative_prompt else None

        # SDXL Turbo is optimized for 1-4 inference steps and 0.0 guidance scale.
        # Height and width must be supported by the model (e.g. multiples of 8).
        # On MPS, batch generation sometimes can cause memory issues depending on standard RAM, but 1-2 images should be fine.
        images = self.pipeline(
            prompt=prompts,
            negative_prompt=negative_prompts,
            num_inference_steps=4,
            guidance_scale=0.0,
            height=height,
            width=width,
        ).images

        results = []
        for img in images:
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            results.append(buf.getvalue())

        print(f"Generation complete.")
        return results
