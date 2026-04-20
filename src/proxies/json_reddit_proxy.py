"""Reddit proxy that uses the public .json endpoint (no API key required)."""

import time
from typing import Literal, Optional, List

import requests

from ..core.logging_config import get_logger
from ..entities.configs.proxies.reddit import JsonRedditConfig
from ..entities.reddit_post import RedditPost
from ..proxies.interfaces import IRedditProxy


class JsonRedditProxy(IRedditProxy):
    _HEADERS = {
        "User-Agent": "VideoGenerator/1.0",
    }

    _REQUEST_DELAY = 1.5

    def __init__(self, config: JsonRedditConfig):
        self._logger = get_logger(__name__)
        self._config = config

    _DEFAULT_COMMUNITY_ICON = (
        "https://styles.redditmedia.com/t5_2r0ij/styles/"
        "communityIcon_yor9myhxz5x11.png"
    )

    def _parse_post_data(self, post_data: dict) -> RedditPost:
        title = post_data.get("title", "")
        selftext = post_data.get("selftext", "")
        subreddit = post_data.get("subreddit_name_prefixed", "")
        author = post_data.get("author", "[unknown]")
        permalink = post_data.get("permalink", "")
        url = f"https://www.reddit.com{permalink}" if permalink else None

        sr_detail = post_data.get("sr_detail", {})
        community_icon = sr_detail.get("community_icon", "") or sr_detail.get(
            "icon_img", ""
        )
        if community_icon and "?" in community_icon:
            community_icon = community_icon.split("?")[0]
        if not community_icon:
            community_icon = self._DEFAULT_COMMUNITY_ICON

        return RedditPost(
            title=title,
            content=selftext,
            community=subreddit,
            author=f"u/{author}",
            community_url_photo=community_icon,
            url=url,
            score=post_data.get("score"),
            num_comments=post_data.get("num_comments"),
        )

    def get_reddit_post(self, url: str) -> RedditPost:
        json_url = url.rstrip("/") + ".json?sr_detail=true"
        response = requests.get(json_url, headers=self._HEADERS, timeout=15)
        response.raise_for_status()

        data = response.json()
        post_data = data[0]["data"]["children"][0]["data"]
        post = self._parse_post_data(post_data)

        self._logger.info(
            "Fetched post '%s' from %s by %s", post.title[:60], post.community, post.author
        )
        return post

    def list_subreddit_posts(
        self,
        subreddit: str,
        sort: Literal["top", "new", "hot"] = "top",
        time_filter: Literal["hour", "day", "week", "month", "year", "all"] = "day",
        limit: int = 25,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> List[RedditPost]:
        subreddit = subreddit.lstrip("r/")
        collected: List[RedditPost] = []
        after: Optional[str] = None
        page_size = min(limit * 2, 100)
        max_pages = 5

        for page in range(max_pages):
            url = f"https://www.reddit.com/r/{subreddit}/{sort}.json"
            params: dict = {"limit": page_size, "raw_json": 1}
            if sort == "top":
                params["t"] = time_filter
            if after:
                params["after"] = after

            if page > 0:
                time.sleep(self._REQUEST_DELAY)

            response = requests.get(
                url, headers=self._HEADERS, params=params, timeout=15
            )
            response.raise_for_status()

            listing = response.json().get("data", {})
            children = listing.get("children", [])
            after = listing.get("after")

            for child in children:
                if child.get("kind") != "t3":
                    continue
                post_data = child["data"]

                if post_data.get("stickied"):
                    continue
                selftext = post_data.get("selftext", "")
                if not selftext.strip():
                    continue

                char_count = len(selftext)
                if min_chars is not None and char_count < min_chars:
                    continue
                if max_chars is not None and char_count > max_chars:
                    continue

                collected.append(self._parse_post_data(post_data))
                if len(collected) >= limit:
                    break

            if len(collected) >= limit or not after:
                break

        self._logger.info(
            "Listed %d posts from r/%s (%s/%s)", len(collected), subreddit, sort, time_filter
        )
        return collected
