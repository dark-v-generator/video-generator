from os import path
import os
from pathlib import Path
from typing import List
import uuid
from entities.captions import Captions
from entities.config import MainConfig
from entities.cover import RedditCover
from entities.editor import audio_clip, image_clip
from entities.history import History
from entities.reddit_video import RedditHistory
from proxies import reddit_proxy
import proxies.open_api_proxy as open_api_proxy
from services import captions_service, cover_service, speech_service, video_service
from proglog import ProgressBarLogger, TqdmProgressBarLogger

REDDIT_HISTORY_FILE_NAME = "history.yaml"
REGULAR_SPEECH_FILE_NAME = "regular_speech.mp3"
SPEECH_FILE_NAME = "regular_speech.mp3"
CAPTIONS_FILE_NAME = "captions.yaml"
COVER_FILE_NAME = "cover.png"
FINAL_VIDEO_FILE_NAME = "final_video.mp4"

def srcap_reddit_post(post_url: str, config: MainConfig) -> RedditHistory:
    reddit_post = reddit_proxy.get_reddit_post(post_url)
    history = open_api_proxy.enhance_history(reddit_post.title, reddit_post.content)
    cover = RedditCover(
        image_url=reddit_post.community_url_photo,
        author=reddit_post.author,
        community=reddit_post.community,
        title=history.title,
    )
    id = str(uuid.uuid4())
    folder_path = path.join(config.histories_path, id)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    history_path = path.join(folder_path, REDDIT_HISTORY_FILE_NAME)
    reddit_history = RedditHistory(
        id=id,
        cover=cover,
        history=history,
        folder_path=str(Path(folder_path).resolve())
    )
    reddit_history.save_yaml(history_path)
    return reddit_history


def get_reddit_history(id: str, config: MainConfig) -> RedditHistory:
    history_path = path.join(config.histories_path, id, REDDIT_HISTORY_FILE_NAME)
    if not os.path.isfile(history_path):
        return None
    reddit_history = RedditHistory.from_yaml(history_path)
    return reddit_history

def save_reddit_history(reddit_history: RedditHistory, config: MainConfig):
    folder_path = path.join(config.histories_path, reddit_history.id)
    history_path = path.join(folder_path, REDDIT_HISTORY_FILE_NAME)
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)
    reddit_history.save_yaml(history_path)

def list_histories(config: MainConfig) -> List[RedditHistory]:
    if not os.path.isdir(config.histories_path):
        return []
    directories = os.listdir(config.histories_path)
    result = [get_reddit_history(directory, config) for directory in directories]
    return [x for x in result if x is not None]

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

def generate_captions(reddit_history: RedditHistory, rate: float, config: MainConfig) -> None:
    history = reddit_history.history
    text = __get_speech_text(reddit_history.history)
    regular_speech_path = path.join(reddit_history.folder_path, REGULAR_SPEECH_FILE_NAME) 
    captions_path = path.join(reddit_history.folder_path, CAPTIONS_FILE_NAME)
    speech_service.synthesize_speech(text, history.gender, 1.0, regular_speech_path)
    captions = captions_service.generate_captions_from_file(regular_speech_path)
    captions.with_speed(rate).save_yaml(captions_path)
    reddit_history.captions_path = str(Path(captions_path).resolve())
    reddit_history.regular_speech_path = str(Path(regular_speech_path).resolve())
    save_reddit_history(reddit_history, config)

def generate_speech(reddit_history: RedditHistory, rate: float) -> RedditHistory:
    history = reddit_history.history
    text = __get_speech_text(reddit_history.history)
    speech_path = path.join(reddit_history.folder_path, SPEECH_FILE_NAME)
    speech_service.synthesize_speech(text, history.gender, rate, speech_path)
    return RedditHistory(
        **reddit_history.model_dump(),
        speech_path=speech_path,
    )

def generate_cover(reddit_history: RedditHistory, config: MainConfig) -> RedditHistory:
    cover_path = path.join(reddit_history.folder_path, COVER_FILE_NAME)
    cover_service.generate_reddit_cover(
        reddit_cover=reddit_history.cover,
        output_path=cover_path,
        config=config.cover_config
    )
    reddit_history.cover_path = str(Path(cover_path).resolve())
    save_reddit_history(reddit_history, config)

def generate_reddit_video(
        reddit_history: RedditHistory, 
        config: MainConfig,
        logger: ProgressBarLogger = TqdmProgressBarLogger()
    ) -> None:
    if reddit_history.speech_path:
        speech = audio_clip.AudioClip(reddit_history.speech_path)
    if reddit_history.captions_path:
        captions = Captions.from_yaml(reddit_history.captions_path)
    if reddit_history.cover_path:
        cover = image_clip.ImageClip(reddit_history.cover_path)
    print("Generating video compilation...")
    background_video = video_service.create_video_compilation(
        speech.clip.duration,
        config.video_config,
        logger=logger
    )
    
    final_video = video_service.generate_video(
        audio=speech,
        background_video=background_video,
        cover=cover,
        config=config.video_config,
        captions=captions,
    )

    video_path = path.join(reddit_history.folder_path, FINAL_VIDEO_FILE_NAME)
    if config.video_config.low_quality:
        final_video.clip.write_videofile(
            video_path,
            preset="ultrafast",
            fps=15,
            logger=logger
        )
    else:
        final_video.clip.write_videofile(
            video_path, 
            preset="veryfast",
            logger=logger
        )
