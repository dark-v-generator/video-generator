import tempfile
import imgkit
from entities import config
from entities.editor import image_clip

HTML_TEMPLATE = """
<!DOCTYPE html>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sigmar&display=swap" rel="stylesheet">
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
            font-family: {title_font_family};
        }}
        .subtitle {{
            font-size: {subtitle_font_size}px;
            color: {subtitle_font_color};
            font-family: {subtitle_font_family};
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

def __generate_html_cover(title: str, output_path: str, config: config.CoverConfig = config.CoverConfig()):
    html_content = HTML_TEMPLATE.format(
        background_color=config.background_color,
        title_font_size=config.title_font_size,
        title_font_color=config.title_font_color,
        subtitle_font_size=config.subtitle_font_size,
        subtitle_font_color=config.subtitle_font_color,
        title=title,
        subtitle=config.subtitle,
        padding=config.padding,
        rounding_radius=config.rounding_radius,
        title_font_family=config.title_font_family,
        subtitle_font_family=config.subtitle_font_family,
    )

    tmp_html_path = f"{tempfile.mktemp()}.html"
    with open(tmp_html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    options = {
        'format': 'png',
        'transparent': ''
    }
    imgkit.from_file(tmp_html_path, output_path, options=options)

def generate_cover(title: str, config: config.CoverConfig = config.CoverConfig()) -> image_clip.ImageClip:
    output_path = f"{tempfile.mktemp()}.png"
    __generate_html_cover(title, output_path, config)
    print(f"Cover generated at {output_path}")
    return image_clip.ImageClip(output_path)