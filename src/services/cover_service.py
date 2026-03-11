from dataclasses import dataclass
from ..adapters.proxies.interfaces import ICoverProxy
from ..entities.cover import RedditCover
from ..entities.editor.image_clip import ImageClip


@dataclass
class CoverResult:
    clip: ImageClip
    bytes: bytes


class CoverService:
    """Cover generation service that returns a CoverResult"""

    def __init__(self, cover_proxy: ICoverProxy):
        self._cover_proxy = cover_proxy

    async def generate_cover(self, cover: RedditCover) -> CoverResult:
        """Generate cover image and return a CoverResult"""
        cover_bytes = await self._cover_proxy.create_reddit_cover(
            title=cover.title,
            community=cover.community,
            author=cover.author,
            community_url_photo=cover.image_url,
        )
        clip = ImageClip(bytes=cover_bytes)
        return CoverResult(clip=clip, bytes=cover_bytes)
