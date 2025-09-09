from bs4 import BeautifulSoup, ResultSet, Tag
from pydantic import BaseModel, Field
import requests
import re
from urllib.parse import urlparse
from src.core.logging_config import get_logger

logger = get_logger(__name__)


class RedditPost(BaseModel):
    title: str = Field("", title="Title of the Reddit post")
    content: str = Field("", title="Content of the Reddit post")
    community: str = Field("", title="Community of the Reddit post")
    author: str = Field("", title="Author of the Reddit post")
    community_url_photo: str = Field("", title="URL of the community photo")


def get_reddit_post(url) -> RedditPost:
    logger.info(f"Fetching Reddit post: {url}")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }

    response = requests.get(url, headers=headers, timeout=15)
    logger.debug(f"Reddit response: status={response.status_code}, bytes={len(response.content)}")
    html_doc = response.text
    soup = BeautifulSoup(html_doc, "html.parser")

    post = soup.find("shreddit-post")
    if post is None:
        logger.warning("Could not find 'shreddit-post' element. Falling back to meta parsing.")
        return __fallback_parse_from_meta(soup, url)

    reddit_post_params = {}
    title_tag = post.find("h1")
    if title_tag is None:
        logger.warning("Post 'h1' title not found inside 'shreddit-post'. Using empty title.")
        reddit_post_params["title"] = ""
    else:
        reddit_post_params["title"] = (title_tag.text or "").strip()
    reddit_post_params["community"] = post.find(
        "a", class_="subreddit-name"
    ).text.strip()
    reddit_post_params["author"] = __get_author_name(post)
    reddit_post_params["community_url_photo"] = __get_community_url_photo(post)
    reddit_post_params["content"] = __get_post_content(post)

    logger.info("Reddit post parsed successfully via shreddit-post markup")
    return RedditPost(**reddit_post_params)


def __get_community_url_photo(post: Tag) -> str:
    DEFAUL_URL_PHOTO = (
        "https://styles.redditmedia.com/t5_2r0ij/styles/communityIcon_yor9myhxz5x11.png"
    )
    try:
        return post.find("faceplate-tracker").find("img")["src"]
    except Exception as e:
        logger.warning(f"Failed to parse community image URL: {e}")
        return DEFAUL_URL_PHOTO


def __get_post_content(post: Tag) -> str:
    try:
        container = post.find("div", class_="text-neutral-content")
        if container is None:
            logger.warning("Content container 'div.text-neutral-content' not found. Returning empty content.")
            return ""
        lines: ResultSet[Tag] = container.find_all("p")
        content = ""
        for line in lines:
            content += line.text.strip() + "\n"
        return content
    except Exception as e:
        logger.warning(f"Failed to parse post content: {e}")
        return ""


def __get_author_name(post: Tag) -> str:
    a = post.find("a", class_="author-name")
    if a is None:
        return "[usuario desconhecido]"
    return a.text.strip()


def __fallback_parse_from_meta(soup: BeautifulSoup, url: str) -> RedditPost:
    title = ""
    content = ""
    community = __parse_subreddit_from_url(url)
    author = "[usuario desconhecido]"
    image_url = ""

    try:
        og_title = soup.find("meta", attrs={"property": "og:title"})
        if og_title and og_title.get("content"):
            title = og_title["content"].strip()
    except Exception:
        pass

    try:
        og_desc = soup.find("meta", attrs={"property": "og:description"})
        if og_desc and og_desc.get("content"):
            content = og_desc["content"].strip()
    except Exception:
        pass

    try:
        og_image = soup.find("meta", attrs={"property": "og:image"})
        if og_image and og_image.get("content"):
            image_url = og_image["content"].strip()
    except Exception:
        pass

    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    logger.info("Reddit post parsed via meta fallback")
    return RedditPost(
        title=title,
        content=content,
        community=community,
        author=author,
        community_url_photo=image_url
    )


def __parse_subreddit_from_url(url: str) -> str:
    try:
        path = urlparse(url).path
        match = re.search(r"/r/([^/]+)/", path)
        if match:
            return match.group(1)
    except Exception:
        pass
    return ""
