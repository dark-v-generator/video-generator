from bs4 import BeautifulSoup, ResultSet, Tag
import requests

from ...adapters.proxies.interfaces import IRedditProxy
from ...entities.reddit import RedditPost

from ...core.logging_config import get_logger


class BS4RedditProxy(IRedditProxy):
    def __init__(self):
        self.logger = get_logger(__name__)

    def get_reddit_post(self, url: str) -> RedditPost:
        response = requests.get(url)
        html_doc = response.text
        soup = BeautifulSoup(html_doc, "html.parser")
        reddit_post_params = {}
        post = soup.find("shreddit-post")
        reddit_post_params["title"] = post.find("h1").text.strip()
        reddit_post_params["community"] = post.find(
            "a", class_="subreddit-name"
        ).text.strip()
        reddit_post_params["author"] = self.__get_author_name(post)
        reddit_post_params["community_url_photo"] = self.__get_community_url_photo(post)
        reddit_post_params["content"] = self.__get_post_content(post)

        return RedditPost(**reddit_post_params)

    def __get_community_url_photo(self, post: Tag) -> str:
        DEFAUL_URL_PHOTO = "https://styles.redditmedia.com/t5_2r0ij/styles/communityIcon_yor9myhxz5x11.png"
        try:
            return post.find("faceplate-tracker").find("img")["src"]
        except Exception as e:
            self.logger.warning("Error getting community url photo", exc_info=e)
            return DEFAUL_URL_PHOTO

    def __get_post_content(self, post: Tag) -> str:
        lines: ResultSet[Tag] = post.find(
            "div", class_="text-neutral-content"
        ).find_all("p")
        content = ""
        for line in lines:
            content += line.text.strip() + "\n"
        return content

    def __get_author_name(self, post: Tag) -> str:
        a = post.find("a", class_="author-name")
        if a is None:
            return "[usuario desconhecido]"
        return a.text.strip()
