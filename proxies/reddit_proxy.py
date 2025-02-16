from bs4 import BeautifulSoup, ResultSet, Tag
from pydantic import BaseModel, Field
import requests


class RedditPost(BaseModel):
    title: str = Field("", title="Title of the Reddit post")
    content: str = Field("", title="Content of the Reddit post")
    community: str = Field("", title="Community of the Reddit post")
    author: str = Field("", title="Author of the Reddit post")
    community_url_photo: str = Field("", title="URL of the community photo")


def get_reddit_post(url) -> RedditPost:
    response = requests.get(url)
    html_doc = response.text
    soup = BeautifulSoup(html_doc, "html.parser")
    reddit_post_params = {}
    post = soup.find("shreddit-post")
    reddit_post_params["title"] = post.find("h1").text.strip()
    reddit_post_params["community"] = post.find(
        "a", class_="subreddit-name"
    ).text.strip()
    reddit_post_params["author"] = __get_author_name(post)
    reddit_post_params["community_url_photo"] = __get_community_url_photo(post)
    reddit_post_params["content"] = __get_post_content(post)

    return RedditPost(**reddit_post_params)


def __get_community_url_photo(post: Tag) -> str:
    DEFAUL_URL_PHOTO = (
        "https://styles.redditmedia.com/t5_2r0ij/styles/communityIcon_yor9myhxz5x11.png"
    )
    try:
        return post.find("faceplate-tracker").find("img")["src"]
    except Exception as e:
        print(e)
        return DEFAUL_URL_PHOTO


def __get_post_content(post: Tag) -> str:
    lines: ResultSet[Tag] = post.find("div", class_="text-neutral-content").find_all(
        "p"
    )
    content = ""
    for line in lines:
        content += line.text.strip() + "\n"
    return content


def __get_author_name(post: Tag) -> str:
    a = post.find("a", class_="author-name")
    if a is None:
        return "[usuario desconhecido]"
    return a.text.strip()
