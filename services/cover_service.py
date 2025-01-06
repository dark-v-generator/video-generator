import os
from tempfile import gettempdir, mktemp
from PIL import Image, ImageDraw, ImageFont

def draw_rounded_rectangle(draw, xy, radius, fill):
    x1, y1, x2, y2 = xy
    # Draw the main rectangle parts
    draw.rectangle([x1 + radius, y1, x2 - radius, y2], fill=fill)
    draw.rectangle([x1, y1 + radius, x2, y2 - radius], fill=fill)
    # Draw the corners
    draw.pieslice([x1, y1, x1 + 2 * radius, y1 + 2 * radius], 180, 270, fill=fill)
    draw.pieslice([x2 - 2 * radius, y1, x2, y1 + 2 * radius], 270, 360, fill=fill)
    draw.pieslice([x1, y2 - 2 * radius, x1 + 2 * radius, y2], 90, 180, fill=fill)
    draw.pieslice([x2 - 2 * radius, y2 - 2 * radius, x2, y2], 0, 90, fill=fill)

def wrap_text(text, font, max_width):
    lines = []
    words = text.split()
    current_line = ""
    for word in words:
        test_line = f"{current_line} {word}".strip()
        width, _ = font.getbbox(test_line)[2:4]
        if width <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines

def generate_cover(title, subtitle="", output_path=None):
    # Initial image settings
    base_width, base_height = 2000, 650
    radius = 30
    padding = 100
    background_color = (255, 255, 255, 0)  # Transparent background
    rectangle_color = (255, 255, 255)  # White rectangle
    title_color = (0, 0, 0)  # Black text
    subtitle_color = '#5C5C5C'  # Gray text

    # Create a font object
    try:
        title_font = ImageFont.truetype("assets/kite_one.ttf", 150)
        subtitle_font = ImageFont.truetype("assets/kite_one.ttf", 100)
    except IOError:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()

    # Create a dummy image to calculate text sizes
    dummy_image = Image.new('RGBA', (1, 1), (255, 255, 255, 0))
    draw = ImageDraw.Draw(dummy_image)
    
    # Calculate text sizes
    title_lines = wrap_text(title, title_font, base_width - 2 * padding)
    subtitle_lines = wrap_text(subtitle, subtitle_font, base_width - 2 * padding)
    
    # Calculate total height and width
    title_height = sum(draw.textbbox((0, 0), line, font=title_font)[3] - draw.textbbox((0, 0), line, font=title_font)[1] for line in title_lines)
    subtitle_height = sum(draw.textbbox((0, 0), line, font=subtitle_font)[3] - draw.textbbox((0, 0), line, font=subtitle_font)[1] for line in subtitle_lines)

    rectangle_width = base_width
    rectangle_height = title_height + subtitle_height + 3 * padding

    # Create the final image
    image = Image.new('RGBA', (rectangle_width, rectangle_height), background_color)
    draw = ImageDraw.Draw(image)

    # Draw the rounded rectangle
    draw_rounded_rectangle(draw, (0, 0, rectangle_width, rectangle_height), radius, rectangle_color)

    # Calculate positions for centered text
    title_x = (rectangle_width - (base_width - 2 * padding)) / 2 + padding
    title_y = (rectangle_height - (title_height + subtitle_height + padding)) / 2

    subtitle_x = (rectangle_width - (base_width - 2 * padding)) / 2 + padding
    subtitle_y = title_y + title_height + padding

    # Draw text lines
    y_offset = title_y
    for line in title_lines:
        line_width = draw.textbbox((0, 0), line, font=title_font)[2] - draw.textbbox((0, 0), line, font=title_font)[0]
        x_offset = (rectangle_width - line_width) / 2
        draw.text((x_offset, y_offset), line, font=title_font, fill=title_color)
        y_offset += draw.textbbox((0, 0), line, font=title_font)[3] - draw.textbbox((0, 0), line, font=title_font)[1]

    y_offset = subtitle_y
    for line in subtitle_lines:
        line_width = draw.textbbox((0, 0), line, font=subtitle_font)[2] - draw.textbbox((0, 0), line, font=subtitle_font)[0]
        x_offset = (rectangle_width - line_width) / 2
        draw.text((x_offset, y_offset), line, font=subtitle_font, fill=subtitle_color)
        y_offset += draw.textbbox((0, 0), line, font=subtitle_font)[3] - draw.textbbox((0, 0), line, font=subtitle_font)[1]

    if not output_path:
        output_path = os.path.join(gettempdir(), f"{mktemp()}.png")
    image.save(output_path)
    return output_path
