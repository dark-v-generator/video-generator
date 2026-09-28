"""Record what the TikTok Studio fetches, so the reader can be written against it.

Opens the publisher's profile the same way the Studio reader does, visits the
content list (scrolling to load more rows) and one video's analytics page,
and writes every JSON response to disk. It parses nothing: the dump is the
evidence the parser in src/proxies/tiktok_studio_proxy.py is written and
tested against, and rerunning this is how that parser is fixed when the
Studio changes.

Output, under <out>/<UTC timestamp>/:
    NNN-<host>-<path>.json   {"url", "status", "method", "body"} per JSON response
    responses.tsv            every XHR/fetch response: n, status, type, url
    page-NN-<step>.png       a screenshot after each step

Usage (on the server, through `just prod-tiktok-studio-probe`):
    uv run python scripts/tiktok_studio_probe.py
    uv run python scripts/tiktok_studio_probe.py --video-id 7412345678901234567
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from patchright.async_api import Page, Response

from src.core.container import container
from src.proxies.factories import TikTokStudioProxyFactory
from src.proxies.tiktok_studio_proxy import (
    ANALYTICS_URL_TEMPLATE,
    CONTENT_LIST_URL,
    raise_if_logged_out,
    studio_page,
)

DEFAULT_OUT = ".storage/tiktok_studio_probe"
# The Studio keeps polling, so "network idle" never comes; wait a fixed time.
SETTLE_MS = 8000
VIDEO_LINK = re.compile(r"/(?:video|analytics)/(\d{15,})")
# Only used when the list has no links to follow: a TikTok post id in a body.
VIDEO_ID_IN_BODY = re.compile(
    r'"(?:item_id|itemId|aweme_id|awemeId|video_id|id)"\s*:\s*"?(\d{18,20})'
)


class Recorder:
    """Writes each XHR/fetch response as it arrives."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.count = 0
        self.json_count = 0
        self.bodies: list[str] = []
        self._pending: set[asyncio.Task] = set()
        self._index = (directory / "responses.tsv").open("w", encoding="utf-8")
        self._index.write("n\tstatus\tcontent-type\turl\n")

    def on_response(self, response: Response) -> None:
        if response.request.resource_type not in ("xhr", "fetch"):
            return
        task = asyncio.ensure_future(self._record(response))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _record(self, response: Response) -> None:
        self.count += 1
        n = self.count
        content_type = response.headers.get("content-type", "")
        self._index.write(f"{n}\t{response.status}\t{content_type}\t{response.url}\n")
        if "json" not in content_type:
            return
        try:
            text = await response.text()
        except Exception as exc:  # the page moved on before the body was read
            self._index.write(f"{n}\t-\tbody unavailable: {exc}\t{response.url}\n")
            return
        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            body = text
        self.json_count += 1
        self.bodies.append(text)
        url = urlparse(response.url)
        path = url.path.strip("/").replace("/", "_")[:80] or "root"
        name = f"{n:03d}-{url.hostname}-{path}.json"
        record = {
            "url": response.url,
            "status": response.status,
            "method": response.request.method,
            "body": body,
        }
        (self.directory / name).write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    async def drain(self) -> None:
        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)
        self._index.flush()

    def close(self) -> None:
        self._index.close()


async def screenshot(page: Page, directory: Path, step: int, name: str) -> None:
    await page.screenshot(path=str(directory / f"page-{step:02d}-{name}.png"))


async def scroll_to_end(page: Page, scrolls: int) -> None:
    # The content table may scroll inside its own container, so wheel over
    # the middle of the page as well as scrolling the document.
    viewport = await page.evaluate("[window.innerWidth, window.innerHeight]")
    await page.mouse.move(viewport[0] / 2, viewport[1] / 2)
    for _ in range(scrolls):
        await page.mouse.wheel(0, 4000)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(2500)


async def first_video_id(page: Page, recorder: Recorder) -> Optional[str]:
    hrefs = await page.evaluate(
        "Array.from(document.querySelectorAll('a[href]')).map(a => a.href)"
    )
    for href in hrefs:
        found = VIDEO_LINK.search(href)
        if found:
            return found.group(1)
    for text in recorder.bodies:
        found = VIDEO_ID_IN_BODY.search(text)
        if found:
            return found.group(1)
    return None


async def probe(out: Path, video_id: Optional[str], scrolls: int) -> Path:
    main_config = container.main_config()
    studio_config = main_config.proxies.tiktok_studio_config
    profile = TikTokStudioProxyFactory.profile(
        studio_config, main_config.proxies.tiktok_publisher_config
    )
    directory = out / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    directory.mkdir(parents=True, exist_ok=True)
    print(f"🔎 Perfil {profile}")
    print(f"📁 Gravando em {directory}")

    recorder = Recorder(directory)
    try:
        async with studio_page(
            profile,
            headless=studio_config.headless,
            page_timeout_seconds=studio_config.page_timeout_seconds,
        ) as page:
            page.on("response", recorder.on_response)

            await page.goto(CONTENT_LIST_URL, wait_until="domcontentloaded")
            await page.wait_for_timeout(SETTLE_MS)
            await screenshot(page, directory, 1, "content")
            raise_if_logged_out(page)

            await scroll_to_end(page, scrolls)
            await screenshot(page, directory, 2, "content-scrolled")
            await recorder.drain()

            video_id = video_id or await first_video_id(page, recorder)
            if video_id is None:
                raise RuntimeError(
                    "Nenhum id de vídeo na lista de conteúdo; rode de novo com "
                    "--video-id ID (os ids estão no dump)."
                )
            print(f"📊 Analytics do vídeo {video_id}")
            await page.goto(
                ANALYTICS_URL_TEMPLATE.format(video_id=video_id),
                wait_until="domcontentloaded",
            )
            await page.wait_for_timeout(SETTLE_MS)
            raise_if_logged_out(page)
            await scroll_to_end(page, 2)
            await screenshot(page, directory, 3, "analytics")
            await recorder.drain()
    finally:
        await recorder.drain()
        recorder.close()
        print(
            f"✅ {recorder.count} respostas XHR/fetch, "
            f"{recorder.json_count} JSON gravadas em {directory}"
        )
    return directory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default=DEFAULT_OUT, type=Path)
    parser.add_argument(
        "--video-id", help="Video whose analytics to open (default: the first listed)"
    )
    parser.add_argument(
        "--scrolls", type=int, default=5, help="Scrolls down the content list"
    )
    args = parser.parse_args()
    try:
        asyncio.run(probe(args.out, args.video_id, args.scrolls))
    except Exception as exc:
        print(f"❌ {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
