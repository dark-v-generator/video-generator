import io
import random
import textwrap
from typing import List, Optional

from PIL import Image, ImageDraw, ImageFont

from .interfaces import IImageGeneratorProxy


class MockImageGeneratorProxy(IImageGeneratorProxy):
    """Generates placeholder images with random-colored backgrounds and text overlay."""

    def generate_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
    ) -> List[bytes]:
        images: List[bytes] = []
        for _ in range(num_images):
            r = random.randint(30, 200)
            g = random.randint(30, 200)
            b = random.randint(30, 200)
            img = Image.new("RGB", (width, height), (r, g, b))
            draw = ImageDraw.Draw(img)

            font_size = max(20, width // 25)
            try:
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

            max_chars = max(15, width // (font_size // 2))
            wrapped = textwrap.fill(prompt, width=max_chars)

            text_color = (255, 255, 255) if (r + g + b) / 3 < 140 else (0, 0, 0)
            bbox = draw.multiline_textbbox((0, 0), wrapped, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            x = (width - text_w) // 2
            y = (height - text_h) // 2

            draw.multiline_text(
                (x, y), wrapped, fill=text_color, font=font, align="center"
            )

            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            images.append(buffer.getvalue())
        return images
