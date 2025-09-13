from playwright.async_api import async_playwright

from ..adapters.repositories.interfaces import IConfigRepository
from .interfaces import ICoverService
from ..entities.cover import RedditCover
from ..entities.config import MainConfig

REDDIT_COVER_HTML = """
<!DOCTYPE html>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,100..900;1,14..32,100..900&family=Sigmar&display=swap" rel="stylesheet">
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <style>
    body {{
      margin: 0;
      padding: 0;
      background: transparent;
    }}
    
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


class CoverService(ICoverService):
    """Cover generation service implementation"""

    def __init__(self, config_repository: IConfigRepository):
        self._config_repository = config_repository

    async def generate_cover(self, cover: RedditCover) -> bytes:
        """Generate cover image and return PNG bytes"""
        config = self._config_repository.load_config()
        html_content = self._generate_reddit_cover_html(cover, config.cover_config)

        async with async_playwright() as p:
            browser = await p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            page = await browser.new_page()

            # Set viewport for consistent rendering
            await page.set_viewport_size({"width": 2050, "height": 1200})

            # Set HTML content
            await page.set_content(html_content.decode("utf-8"))

            # Wait for fonts to load
            await page.wait_for_load_state("networkidle")

            # Take screenshot of the cover element with transparency
            cover_element = await page.query_selector(".post-cover")
            if cover_element:
                png_bytes = await cover_element.screenshot(
                    type="png", omit_background=True
                )
            else:
                # Fallback to full page screenshot with transparency
                png_bytes = await page.screenshot(
                    type="png", full_page=True, omit_background=True
                )

            await browser.close()
            return png_bytes

    def _generate_reddit_cover_html(
        self,
        reddit_cover: RedditCover,
        cover_config,
    ) -> bytes:
        """Generate Reddit cover file"""
        html_content = REDDIT_COVER_HTML.format(
            title=reddit_cover.title,
            community=reddit_cover.community,
            post_author=reddit_cover.author,
            community_url_photo=reddit_cover.image_url,
            title_font_size=cover_config.title_font_size,
        )

        return bytes(html_content, "UTF-8")
