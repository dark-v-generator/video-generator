"""Reddit proxy that uses OAuth-backed Reddit .json endpoints."""

import time
from typing import Literal, Optional, List

import requests
from requests.auth import HTTPBasicAuth

from ..core.logging_config import get_logger
from ..entities.configs.proxies.reddit import JsonRedditConfig
from ..entities.reddit_post import RedditPost
from ..proxies.reddit_availability import (
    assert_reddit_post_data_available,
    is_unavailable_reddit_post_data,
)
from ..proxies.interfaces import IRedditProxy


class JsonRedditProxy(IRedditProxy):
    _TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
    _API_BASE_URL = "https://oauth.reddit.com"
    _TOKEN_EXPIRY_SKEW_SECONDS = 60
    _REQUEST_DELAY = 1.5

    def __init__(
        self,
        config: JsonRedditConfig,
        client_id: str | None = None,
        client_secret: str | None = None,
        user_agent: str | None = None,
    ):
        self._logger = get_logger(__name__)
        self._config = config
        self._client_id = client_id
        self._client_secret = client_secret
        self._user_agent = user_agent or "video-generator/0.1"
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    _DEFAULT_COMMUNITY_ICON = (
        "https://styles.redditmedia.com/t5_2r0ij/styles/"
        "communityIcon_yor9myhxz5x11.png"
    )

    def _require_credentials(self) -> None:
        if self._client_id and self._client_secret:
            return
        raise RuntimeError(
            "Reddit OAuth credentials are required. Set REDDIT_CLIENT_ID and "
            "REDDIT_CLIENT_SECRET in the environment or .env file."
        )

    def _get_access_token(self) -> str:
        self._require_credentials()

        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        response = requests.post(
            self._TOKEN_URL,
            auth=HTTPBasicAuth(self._client_id, self._client_secret),
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": self._user_agent},
            timeout=15,
        )
        response.raise_for_status()

        data = response.json()
        token = data.get("access_token")
        if not token:
            raise RuntimeError("Reddit OAuth did not return an access token.")

        expires_in = int(data.get("expires_in") or 3600)
        self._access_token = token
        self._token_expires_at = (
            now + expires_in - self._TOKEN_EXPIRY_SKEW_SECONDS
        )
        return token

    def _request_json(self, path: str, params: dict | None = None):
        token = self._get_access_token()
        response = requests.get(
            f"{self._API_BASE_URL}{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": self._user_agent,
            },
            params=params,
            timeout=15,
        )
        response.raise_for_status()
        return response.json()

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
            upvote_ratio=post_data.get("upvote_ratio"),
            created_utc=post_data.get("created_utc"),
        )

    def get_reddit_post(self, url: str) -> RedditPost:
        path = url.split("reddit.com", 1)[-1].rstrip("/") + ".json"
        data = self._request_json(path, params={"sr_detail": "true"})
        post_data = data[0]["data"]["children"][0]["data"]
        assert_reddit_post_data_available(post_data, url=url)
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
        subreddit = subreddit.strip().removeprefix("r/").strip("/")
        collected: List[RedditPost] = []
        after: Optional[str] = None
        page_size = min(limit * 2, 100)
        max_pages = 5

        for page in range(max_pages):
            path = f"/r/{subreddit}/{sort}.json"
            params: dict = {"limit": page_size, "raw_json": 1}
            if sort == "top":
                params["t"] = time_filter
            if after:
                params["after"] = after

            if page > 0:
                time.sleep(self._REQUEST_DELAY)

            listing = self._request_json(path, params=params).get("data", {})
            children = listing.get("children", [])
            after = listing.get("after")

            for child in children:
                if child.get("kind") != "t3":
                    continue
                post_data = child["data"]

                if post_data.get("stickied"):
                    continue
                if is_unavailable_reddit_post_data(post_data):
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
