import tempfile
import imgkit
from entities import config
from entities.editor import image_clip

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            display: flex;
            justify-content: center;
            align-items: center;
            text-align: center;
            font-family: {font_family};
        }}
        .container {{
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: {padding}px;
            align-items: center;
            border-radius: {rounding_radius}px;
            background-color: {background_color};
        }}
        .title {{
            font-size: {title_font_size}px;
            color: {title_font_color};
        }}
        .subtitle {{
            font-size: {subtitle_font_size}px;
            color: {subtitle_font_color};
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="title">{title}</div>
        <div class="subtitle">{subtitle}</div>
    </div>
</body>
</html>
"""

def __generate_html_cover(title: str, subtitle: str, output_path: str, config: config.CoverConfig = config.CoverConfig()):
    html_content = HTML_TEMPLATE.format(
        background_color=config.background_color,
        font_family=config.font_family,
        title_font_size=config.title_font_size,
        title_font_color=config.title_font_color,
        subtitle_font_size=config.subtitle_font_size,
        subtitle_font_color=config.subtitle_font_color,
        title=title,
        subtitle=subtitle,
        padding=config.padding,
        rounding_radius=config.rounding_radius
    )

    tmp_html_path = f"{tempfile.mktemp()}.html"
    with open(tmp_html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    options = {
        'format': 'png',
        'transparent': ''
    }
    imgkit.from_file(tmp_html_path, output_path, options=options)

def generate_cover(title: str, subtitle: str, config: config.CoverConfig = config.CoverConfig()) -> image_clip.ImageClip:
    output_path = f"{tempfile.mktemp()}.png"
    __generate_html_cover(title, subtitle, output_path, config)
    print(f"Cover generated at {output_path}")
    return image_clip.ImageClip(output_path)