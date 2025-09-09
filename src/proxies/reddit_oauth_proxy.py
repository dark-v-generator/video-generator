import time
from typing import Optional

import requests
from .interfaces import IRedditProxy
from ..core.config import settings
from ..core.logging_config import get_logger
from ..entities.reddit_post import RedditPost


class RedditOAuthProxy(IRedditProxy):
    _token_cache: dict[str, float | str] = {"access_token": "", "expires_at": 0.0}

    def __init__(self):
        self._logger = get_logger(__name__)

    def get_post(self, url: str) -> RedditPost:
        token = self._get_access_token()

        post_id = self._extract_post_id(url)
        if not post_id:
            raise ValueError("Could not extract post id from URL")

        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": settings.reddit_user_agent,
        }

        # Fetch post using comments endpoint
        comments_url = f"https://oauth.reddit.com/comments/{post_id}.json"
        resp = requests.get(comments_url, headers=headers, params={"raw_json": 1}, timeout=20)
        if resp.status_code == 429:
            self._logger.warning("Reddit API rate limited (429)")
        resp.raise_for_status()

        try:
            data = resp.json()
            post = data[0]["data"]["children"][0]["data"]
        except Exception as e:
            self._logger.error("Unexpected Reddit comments payload structure", exc_info=e)
            raise

        title = post.get("title", "")
        content = post.get("selftext", "")
        community = post.get("subreddit", "")
        author = post.get("author", "[usuario desconhecido]")

        # Fetch subreddit icon via about endpoint
        community_icon = self._fetch_subreddit_icon(community, token)
        if not community_icon:
            community_icon = "https://styles.redditmedia.com/t5_2r0ij/styles/communityIcon_yor9myhxz5x11.png"

        return RedditPost(
            title=title,
            content=content,
            community=community,
            author=author,
            community_url_photo=community_icon,
        )

    def _get_access_token(self) -> str:
        now = time.time()
        cached = self._token_cache.get("access_token") or ""
        expires_at = float(self._token_cache.get("expires_at") or 0)
        if cached and now < expires_at - 30:
            return str(cached)

        if not (settings.reddit_client_id and settings.reddit_client_secret):
            raise RuntimeError("Reddit OAuth credentials are required")

        auth = (settings.reddit_client_id, settings.reddit_client_secret)
        data = {"grant_type": "client_credentials", "scope": "read"}
        headers = {"User-Agent": settings.reddit_user_agent}
        resp = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            data=data,
            auth=auth,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        access_token = payload.get("access_token")
        expires_in = float(payload.get("expires_in", 3600))
        self._token_cache["access_token"] = access_token
        self._token_cache["expires_at"] = now + expires_in
        return str(access_token)

    def _fetch_subreddit_icon(self, subreddit: str, token: str) -> str:
        if not subreddit:
            return ""
        headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": settings.reddit_user_agent,
        }
        url = f"https://oauth.reddit.com/r/{subreddit}/about.json"
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                self._logger.debug(f"subreddit about non-200: {resp.status_code}")
                return ""
            data = resp.json().get("data", {})
            for key in ("community_icon", "icon_img", "header_img"):
                val = data.get(key) or ""
                if isinstance(val, str) and val:
                    return val.replace("&amp;", "&")
            return ""
        except Exception as e:
            self._logger.debug("Failed to fetch subreddit icon", exc_info=e)
            return ""

    def _extract_post_id(self, url: str) -> Optional[str]:
        try:
            parts = url.split("/comments/")
            if len(parts) < 2:
                return None
            tail = parts[1]
            return tail.split("/")[0]
        except Exception:
            return None


