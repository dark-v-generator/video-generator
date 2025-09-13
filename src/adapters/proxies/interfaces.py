from abc import ABC, abstractmethod

from ...entities.reddit import RedditPost
from ...entities.captions import Captions


class IRedditProxy(ABC):
    @abstractmethod
    def get_reddit_post(self, url: str) -> RedditPost:
        """Get a Reddit post from a URL"""
        ...


class IWhisperProxy(ABC):
    @abstractmethod
    def generate_captions(self, audio_path: str) -> Captions:
        """Generate captions from an audio file"""
        ...
