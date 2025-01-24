from bs4 import BeautifulSoup, Tag
import requests

from entities.reddit import RedditPost


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
    reddit_post_params["community_url_photo"] = post.find("faceplate-tracker").find(
        "img"
    )["src"]
    lines = post.find("div", class_="text-neutral-content").find_all("p")
    content = ''
    for line in lines:
        content += line.text.strip() + '\n' 
    reddit_post_params["content"] = content
    return RedditPost(**reddit_post_params)

def __get_author_name(post: Tag) -> str:
    a = post.find("a", class_="author-name")
    if a is None:
        return '[usuario desconhecido]'
    return a.text.strip()