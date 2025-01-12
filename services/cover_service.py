import tempfile
from entities.history import History
from entities.reddit import RedditPost
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

REDDIT_COVER_HTML = """
<!DOCTYPE html>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&family=Sigmar&display=swap" rel="stylesheet">
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <style>
    .post-cover {{
      width: 1950px;
      height: 650px;
      padding: 50px;
      display: flex;
      flex-direction: column;
      background-color: #FFFFFF;
      border-radius: 50px;
      box-shadow: 0px 4px 4px rgba(0, 0, 0, 0.25);
      gap: 10px;
    }}

    .title-container {{
      display: flex;
      align-items: top;
      gap: 10px;
    }}

    .text-container {{
      display: flex;
      flex-direction: row;
      gap: 50px;
      align-items: center;
      height: fit-content;
    }}

    .title-container img {{
      width: 200px;
      height: 200px;
      border-radius: 50%;
      object-fit: cover;
      margin-right: 10px
    }}

    .text-container h1 {{
      font-size: 64px;
      font-weight: bold;
      color: #000000;
      font-family: "Inter", serif;
      height: fit-content;
      margin-right: 50px
    }}

    .text-container h2 {{
      font-size: 48px;
      font-weight: normal;
      color: #5C5C5C;
      font-family: "Inter", serif;
      height: fit-content;
    }}

    .history-title {{
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
    }}
    .history-title h1 {{
        text-align: center;
        font-size: {title_font_size}px;
        font-family: "Inter", serif;
        font-weight: medium;
    }}
  </style>
</head>
<div class="post-cover">
    <div class="title-container">
        <img src="{community_url_photo}" alt="Community photo">
        <div class="text-container">
        <h1>{post_author}</h1>
        <h2>{community}</h2>
        </div>
    </div>
    <div class="history-title">
        <h1>{title}</h1>
    </div>
</div>
</html>
"""


def __generate_html_cover(
    title: str, output_path: str, config: config.CoverConfig = config.CoverConfig()
):
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
    with open(tmp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    options = {"format": "png", "transparent": ""}
    imgkit.from_file(tmp_html_path, output_path, options=options)


def __generate_reddit_cover(
    title: str,
    community: str,
    author: str,
    community_url_photo: str,
    output_path: str,
    config: config.CoverConfig = config.CoverConfig(),
):
    html_content = REDDIT_COVER_HTML.format(
        title=title,
        community=community,
        post_author=author,
        community_url_photo=community_url_photo,
        title_font_size=config.title_font_size,
    )

    tmp_html_path = f"{tempfile.mktemp()}.html"
    with open(tmp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    options = {"format": "png", "transparent": ""}
    imgkit.from_file(tmp_html_path, output_path, options=options)


def generate_cover(
    history: History, cfg: config.CoverConfig = config.CoverConfig()
) -> image_clip.ImageClip:
    output_path = f"{tempfile.mktemp()}.png"
    if cfg.cover_type == config.CoverType.REGULAR:
        __generate_html_cover(title=history.title, output_path=output_path, config=cfg)
    else:
        __generate_reddit_cover(
            title=history.title,
            community=history.reddit_community,
            author=history.reddit_post_author,
            community_url_photo=history.reddit_community_url_photo,
            config=cfg,
            output_path=output_path,
        )
    return image_clip.ImageClip(output_path)
