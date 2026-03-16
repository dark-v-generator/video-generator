"""Generate a placeholder call-to-action PNG for use as an overlay."""
import os
import textwrap
from PIL import Image, ImageDraw, ImageFont


def generate_call_to_action(output_path: str, width: int = 900, height: int = 500):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    margin = 30
    radius = 40
    draw.rounded_rectangle(
        [margin, margin, width - margin, height - margin],
        radius=radius,
        fill=(20, 20, 20, 210),
        outline=(255, 80, 80, 255),
        width=4,
    )

    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 52)
        body_font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
    except (OSError, IOError):
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()

    title = "GOSTOU?"
    body_lines = [
        "CURTA esse vídeo",
        "SIGA para mais histórias",
        "COMENTE sua opinião",
    ]

    draw.text(
        (width // 2, 90),
        title,
        fill=(255, 80, 80, 255),
        font=title_font,
        anchor="mm",
    )

    y = 170
    for line in body_lines:
        draw.text(
            (width // 2, y),
            f"👉  {line}",
            fill=(255, 255, 255, 255),
            font=body_font,
            anchor="mm",
        )
        y += 60

    img.save(output_path, format="PNG")
    print(f"CTA image saved to: {output_path}")


if __name__ == "__main__":
    os.makedirs("assets", exist_ok=True)
    generate_call_to_action("assets/call_to_action.png")
