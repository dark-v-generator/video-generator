from abc import ABC, abstractmethod
from typing import Protocol
from ..entities.reddit_post import RedditPost


class IRedditProxy(ABC):
    @abstractmethod
    def get_post(self, url: str) -> RedditPost:
        """Fetch a Reddit post by URL and return an object with
        attributes: title, content, community, author, community_url_photo.
        """
        ...


