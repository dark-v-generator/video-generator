from typing import Literal, Optional, List

from bs4 import BeautifulSoup, ResultSet, Tag
import requests

from ..proxies.interfaces import IRedditProxy
from ..entities.reddit_post import RedditPost
from ..proxies.reddit_availability import assert_reddit_post_available

from ..core.logging_config import get_logger
from ..entities.configs.proxies.reddit import BS4RedditConfig, JsonRedditConfig


class BS4RedditProxy(IRedditProxy):
    def __init__(self, config: BS4RedditConfig):
        self.logger = get_logger(__name__)
        self.config = config

    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/131.0.0.0 Safari/537.36",
    }

    def get_reddit_post(self, url: str) -> RedditPost:
        response = requests.get(url, headers=self._HEADERS)
        html_doc = response.text
        soup = BeautifulSoup(html_doc, "html.parser")
        reddit_post_params = {}
        post = soup.find("shreddit-post")
        if post is None:
            raise ValueError(
                f"Could not find post content. Reddit may have blocked the request (status {response.status_code})."
            )
        title = post.find("h1").text.strip()
        content = self.__get_post_content(post)
        assert_reddit_post_available(title, content, url=url)

        reddit_post_params["title"] = title
        reddit_post_params["community"] = post.find(
            "a", class_="subreddit-name"
        ).text.strip()
        reddit_post_params["author"] = self.__get_author_name(post)
        reddit_post_params["community_url_photo"] = self.__get_community_url_photo(post)
        reddit_post_params["content"] = content

        return RedditPost(**reddit_post_params)

    def __get_community_url_photo(self, post: Tag) -> str:
        DEFAUL_URL_PHOTO = "https://styles.redditmedia.com/t5_2r0ij/styles/communityIcon_yor9myhxz5x11.png"
        try:
            return post.find("faceplate-tracker").find("img")["src"]
        except Exception as e:
            self.logger.warning("Error getting community url photo", exc_info=e)
            return DEFAUL_URL_PHOTO

    def __get_post_content(self, post: Tag) -> str:
        content_container = post.find("div", class_="text-neutral-content")
        if content_container is None:
            return ""
        lines: ResultSet[Tag] = content_container.find_all("p")
        content = ""
        for line in lines:
            content += line.text.strip() + "\n"
        return content

    def __get_author_name(self, post: Tag) -> str:
        a = post.find("a", class_="author-name")
        if a is None:
            return "[usuario desconhecido]"
        return a.text.strip()

    def list_subreddit_posts(
        self,
        subreddit: str,
        sort: Literal["top", "new", "hot"] = "top",
        time_filter: Literal["hour", "day", "week", "month", "year", "all"] = "day",
        limit: int = 25,
        min_chars: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> List[RedditPost]:
        from .json_reddit_proxy import JsonRedditProxy

        json_proxy = JsonRedditProxy(config=JsonRedditConfig())
        return json_proxy.list_subreddit_posts(
            subreddit=subreddit,
            sort=sort,
            time_filter=time_filter,
            limit=limit,
            min_chars=min_chars,
            max_chars=max_chars,
        )
