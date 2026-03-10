from ..adapters.repositories.interfaces import IConfigRepository
from ..adapters.proxies.interfaces import ICoverProxy
from .interfaces import ICoverService
from ..entities.cover import RedditCover


class CoverService(ICoverService):
    """Cover generation service implementation"""

    def __init__(self, config_repository: IConfigRepository, cover_proxy: ICoverProxy):
        self._config_repository = config_repository
        self._cover_proxy = cover_proxy

    async def generate_cover(self, cover: RedditCover) -> bytes:
        """Generate cover image and return PNG bytes"""
        return await self._cover_proxy.create_reddit_cover(
            title=cover.title,
            community=cover.community,
            author=cover.author,
            community_url_photo=cover.image_url,
        )
