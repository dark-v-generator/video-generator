from bs4 import BeautifulSoup
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
    reddit_post_params["author"] = post.find("a", class_="author-name").text.strip()
    reddit_post_params["community_url_photo"] = post.find("faceplate-tracker").find(
        "img"
    )["src"]
    reddit_post_params["content"] = (
        post.find("div", class_="text-neutral-content").find("p").text.strip()
    )
    return RedditPost(**reddit_post_params)
