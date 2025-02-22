from os import path
import os
from pathlib import Path
import shutil
from typing import List, Optional
import uuid
from src.entities.captions import Captions
from src.entities.config import MainConfig
from src.entities.cover import RedditCover
from src.entities.editor import audio_clip, captions_clip, image_clip
from src.entities.history import History
from src.entities.language import Language
from src.entities.reddit_history import RedditHistory
from src.proxies import reddit_proxy
from src.proxies import open_api_proxy
from src.services import captions_service, cover_service, speech_service, video_service
from proglog import ProgressBarLogger, TqdmProgressBarLogger

REDDIT_HISTORY_FILE_NAME = "history.yaml"
REGULAR_SPEECH_FILE_NAME = "regular_speech.mp3"
SPEECH_FILE_NAME = "speech.mp3"
CAPTIONS_FILE_NAME = "captions.yaml"
COVER_FILE_NAME = "cover.png"
FINAL_VIDEO_FILE_NAME = "final_video.mp4"


def srcap_reddit_post(
    post_url: str,
    enhance_history: bool,
    config: MainConfig,
    language: Language = Language.PORTUGUESE,
) -> RedditHistory:
    reddit_post = reddit_proxy.get_reddit_post(post_url)
    if enhance_history:
        history = open_api_proxy.enhance_history(
            reddit_post.title, reddit_post.content, language=language
        )
    else:
        history = History(
            title=reddit_post.title, content=reddit_post.content, gender="male"
        )
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
        history=history.striped(),
        folder_path=str(Path(folder_path).resolve()),
    )
    reddit_history.save_yaml(history_path)
    return reddit_history


def get_reddit_history(id: str, config: MainConfig) -> Optional[RedditHistory]:
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


def delete_reddit_history(id: str, config: MainConfig) -> None:
    folder_path = path.join(config.histories_path, id)
    shutil.rmtree(folder_path)


def list_histories(config: MainConfig) -> List[RedditHistory]:
    if not os.path.isdir(config.histories_path):
        return []
    directories = os.listdir(config.histories_path)
    result = [get_reddit_history(directory, config) for directory in directories]
    result = [x for x in result if x is not None]
    return sorted(result, key=lambda x: x.last_updated_at, reverse=True)


def divide_reddit_history(
    reddit_history: RedditHistory,
    config: MainConfig,
    number_of_parts: int,
) -> List[RedditHistory]:
    histories = open_api_proxy.divide_history(
        reddit_history.history,
        number_of_parts=number_of_parts,
        language=reddit_history.get_language(),
    )
    reddit_history_params = reddit_history.model_dump()
    reddit_history_params.pop("id")
    reddit_history_params.pop("history")
    reddit_histories = [
        RedditHistory(id=str(uuid.uuid4()), history=history, **reddit_history_params)
        for history in histories
    ]
    for rh in reddit_histories:
        save_reddit_history(rh, config)
    return reddit_histories


def __get_speech_text(history: History) -> str:
    return f"{history.title}\n {history.content}"


def generate_captions(
    reddit_history: RedditHistory,
    rate: float,
    config: MainConfig,
    enhance_captions: bool = True,
) -> None:
    regular_speech_path = path.join(
        reddit_history.folder_path, REGULAR_SPEECH_FILE_NAME
    )
    captions_path = path.join(reddit_history.folder_path, CAPTIONS_FILE_NAME)
    captions = captions_service.generate_captions_from_file(
        regular_speech_path, language=reddit_history.get_language()
    )
    captions = captions.with_speed(rate).stripped()
    if enhance_captions:
        captions = open_api_proxy.enhance_captions(
            captions, reddit_history.history, language=reddit_history.get_language()
        )
    captions.save_yaml(captions_path)
    reddit_history.captions_path = str(Path(captions_path).resolve())
    save_reddit_history(reddit_history, config)


def generate_speech(
    reddit_history: RedditHistory,
    rate: float,
    config: MainConfig,
) -> None:
    history = reddit_history.history
    text = __get_speech_text(reddit_history.history)
    speech_path = path.join(reddit_history.folder_path, SPEECH_FILE_NAME)
    regular_speech_path = path.join(
        reddit_history.folder_path, REGULAR_SPEECH_FILE_NAME
    )

    gender = speech_service.VoiceGender(history.gender)
    speech_service.synthesize_speech(
        text, 
        gender, 
        rate, 
        speech_path,
        language=reddit_history.get_language()
    )
    speech_service.synthesize_speech(
        text, 
        gender, 
        1.0, 
        regular_speech_path,
        language=reddit_history.get_language()
    )
    reddit_history.speech_path = str(Path(speech_path).resolve())
    reddit_history.regular_speech_path = str(Path(regular_speech_path).resolve())
    save_reddit_history(reddit_history, config)


def generate_cover(reddit_history: RedditHistory, config: MainConfig) -> None:
    cover_path = path.join(reddit_history.folder_path, COVER_FILE_NAME)
    cover_service.generate_reddit_cover(
        reddit_cover=reddit_history.cover,
        output_path=cover_path,
        config=config.cover_config,
    )
    reddit_history.cover_path = str(Path(cover_path).resolve())
    save_reddit_history(reddit_history, config)


def generate_reddit_video(
    reddit_history: RedditHistory,
    config: MainConfig,
    low_quality: bool = True,
    logger: ProgressBarLogger = TqdmProgressBarLogger(),
) -> None:
    config.video_config.low_quality = low_quality
    config.video_config.low_resolution = low_quality

    if low_quality:
        size_rate = 400 / config.video_config.height  # fixed 400 height
        config.video_config.width = int(round(config.video_config.width * size_rate))
        config.video_config.height = int(round(config.video_config.height * size_rate))
        config.captions_config.font_size = int(
            round(config.captions_config.font_size * size_rate)
        )
        config.captions_config.stroke_width = int(
            round(config.captions_config.stroke_width * size_rate)
        )
        config.captions_config.marging = int(
            round(config.captions_config.marging * size_rate)
        )
        config.video_config.padding = int(
            round(config.video_config.padding * size_rate)
        )
    speech = None
    captions = None
    cover = None
    if reddit_history.speech_path:
        speech = audio_clip.AudioClip(reddit_history.speech_path)
    if reddit_history.captions_path:
        captions = captions_clip.CaptionsClip(
            captions=Captions.from_yaml(reddit_history.captions_path),
            config=config.captions_config,
        )
    if reddit_history.cover_path:
        cover = image_clip.ImageClip(reddit_history.cover_path)
    print("Generating video compilation...")
    background_video = video_service.create_video_compilation(
        speech.clip.duration, config.video_config, logger=logger
    )

    final_video = video_service.generate_video(
        audio=speech,
        background_video=background_video,
        cover=cover,
        config=config.video_config,
        captions=captions,
    )

    video_path = path.join(
        reddit_history.folder_path, f"{reddit_history.history.title_normalized()}.mp4"
    )
    reddit_history.final_video_path = str(Path(video_path).resolve())
    if low_quality:
        final_video.clip.write_videofile(
            video_path, logger=logger, ffmpeg_params=config.video_config.ffmpeg_params
        )
    else:
        final_video.clip.write_videofile(
            video_path, logger=logger, ffmpeg_params=config.video_config.ffmpeg_params
        )
    save_reddit_history(reddit_history, config)
