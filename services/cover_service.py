import tempfile
from entities.cover import RedditCover
from entities.history import History
import imgkit
from entities import config
from entities.editor import image_clip

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
      padding: 50px;
      background-color: #FFFFFF;
      border-radius: 50px;
      box-shadow: 0px 4px 4px rgba(0, 0, 0, 0.25);
    }}

    .title-container {{
      display: -webkit-box;
    }}

    .text-container {{
      display: -webkit-box;
      -webkit-box-align: center;
    }}

    .title-container img {{
      width: 200px;
      height: 200px;
      border-radius: 50%;
      object-fit: cover;
      margin-right: 30px
    }}

    .text-container h1 {{
      font-size: 64px;
      font-weight: bold;
      color: #000000;
      font-family: "Inter", serif;
      margin-right: 30px
    }}

    .text-container h2 {{
      font-size: 48px;
      font-weight: normal;
      color: #5C5C5C;
      font-family: "Inter", serif;
    }}

    .history-title {{
        display: -webkit-box;
        align-items: center;
        -webkit-box-pack: center;
        padding: 50px;
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
          <h1>{community}</h1>
          <h2>{post_author}</h2>
        </div>
    </div>
    <div class="history-title">
        <h1>{title}</h1>
    </div>
</div>
</html>
"""


def generate_reddit_cover(
    reddit_cover: RedditCover,
    output_path: str,
    config: config.CoverConfig = config.CoverConfig(),
):
    html_content = REDDIT_COVER_HTML.format(
        title=reddit_cover.title,
        community=reddit_cover.community,
        post_author=reddit_cover.author,
        community_url_photo=reddit_cover.image_url,
        title_font_size=config.title_font_size,
    )

    tmp_file = tempfile.NamedTemporaryFile(suffix=".html", delete=False)
    tmp_file.write(bytes(html_content, "UTF-8"))
    file_name = tmp_file.name
    tmp_file.close()

    options = {"--format": "png", "--transparent": ""}
    imgkit.from_file(file_name, output_path, options=options)
