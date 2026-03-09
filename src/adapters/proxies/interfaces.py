from abc import ABC, abstractmethod
from typing import List

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


class IImageGeneratorProxy(ABC):
    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        negative_prompt: str | None,
        width: int = 1024,
        height: int = 1024,
        num_images: int = 1,
    ) -> List[bytes]:
        """Generate a list of images from a prompt"""
        ...
