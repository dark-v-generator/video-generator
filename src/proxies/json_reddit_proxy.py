"""Reddit proxy that uses the public .json endpoint (no API key required)."""

import requests

from ..core.logging_config import get_logger
from ..entities.configs.proxies.reddit import JsonRedditConfig
from ..entities.reddit_post import RedditPost
from ..proxies.interfaces import IRedditProxy


class JsonRedditProxy(IRedditProxy):
    _HEADERS = {
        "User-Agent": "VideoGenerator/1.0",
    }

    def __init__(self, config: JsonRedditConfig):
        self._logger = get_logger(__name__)
        self._config = config

    def get_reddit_post(self, url: str) -> RedditPost:
        json_url = url.rstrip("/") + ".json"
        response = requests.get(json_url, headers=self._HEADERS, timeout=15)
        response.raise_for_status()

        data = response.json()

        # Reddit returns a list of Listings; the first one contains the post.
        post_data = data[0]["data"]["children"][0]["data"]

        title = post_data.get("title", "")
        selftext = post_data.get("selftext", "")
        subreddit = post_data.get("subreddit_name_prefixed", "")
        author = post_data.get("author", "[unknown]")
        community_icon = (
            post_data.get("sr_detail", {}).get("community_icon", "")
            if "sr_detail" in post_data
            else ""
        )
        # community_icon often has query params encoded; strip them
        if community_icon and "?" in community_icon:
            community_icon = community_icon.split("?")[0]

        if not community_icon:
            community_icon = (
                "https://styles.redditmedia.com/t5_2r0ij/styles/"
                "communityIcon_yor9myhxz5x11.png"
            )

        self._logger.info(
            "Fetched post '%s' from %s by u/%s", title[:60], subreddit, author
        )

        return RedditPost(
            title=title,
            content=selftext,
            community=subreddit,
            author=f"u/{author}",
            community_url_photo=community_icon,
        )
