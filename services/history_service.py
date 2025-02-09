from typing import List
from entities.config import CoverConfig
from entities.cover import RedditCover
from entities.history import History
from entities.reddit_video import RedditHistory
from proxies import reddit_proxy
import proxies.open_api_proxy as open_api_proxy
from services import captions_service, cover_service, speech_service

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

def __get_speech_text(history: History) -> str:
    return """
        {title}
    
        {content}
    """.format(
        title=history.title,
        content=history.content
    )

def generate_captions(reddit_history: RedditHistory, rate: float) -> RedditHistory:
    history = reddit_history.history
    text = __get_speech_text(reddit_history.history)
    regular_speech_path = f"{reddit_history.folder_path}/regular_speech.mp3"
    captions_path = f"{reddit_history.folder_path}/captions.yaml"
    speech_service.synthesize_speech(text, history.gender, 1.0, regular_speech_path)
    captions = captions_service.generate_captions_from_file(regular_speech_path)
    captions.with_speed(rate).save_yaml(captions_path)
    return RedditHistory(
        **reddit_history.model_dump(),
        captions_path=captions_path,
        regular_speech_path=regular_speech_path,
    )

def generate_speech(reddit_history: RedditHistory, rate: float) -> RedditHistory:
    history = reddit_history.history
    text = __get_speech_text(reddit_history.history)
    speech_path = f"{reddit_history.folder_path}/speech.mp3"
    speech_service.synthesize_speech(text, history.gender, rate, speech_path)
    return RedditHistory(
        **reddit_history.model_dump(),
        speech_path=speech_path,
    )

def generate_cover(reddit_history: RedditHistory, cover_config: CoverConfig = CoverConfig()) -> RedditHistory:
    cover_path = f"{reddit_history.folder_path}/cover.png"
    cover_service.generate_reddit_cover(
        reddit_cover=reddit_history.cover,
        output_path=cover_path,
        config=cover_config
    )
    return RedditHistory(
        **reddit_history.model_dump(),
        cover_path=cover_path,
    )