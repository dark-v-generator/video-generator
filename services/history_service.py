import os
from typing import List
from entities import config
from entities.cover import RedditCover
from entities.history import History
from entities.reddit_video import RedditHistory
from proxies import reddit_proxy
import proxies.open_api_proxy as open_api_proxy
import yaml

def srcap_reddit_post(post_url: str) -> RedditHistory:
    reddit_post = reddit_proxy.get_reddit_post(post_url)
    history = open_api_proxy.enhance_history(reddit_post.title, reddit_post.content)
    cover = RedditCover(
        image_url=reddit_post.community_url_photo,
        author=reddit_post.author,
        community=reddit_post.community,
        title=history.title,
    )
    return RedditHistory(
        cover=cover,
        history=history
    )

def divide_reddit_history(reddit_video: RedditHistory, number_of_parts) -> List[RedditHistory]:
    histories = open_api_proxy.divide_history(reddit_video.history, number_of_parts=number_of_parts)
    return [RedditHistory(**reddit_video.model_dump(), history=history) for history in histories]
