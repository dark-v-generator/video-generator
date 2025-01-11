import random
from entities.config import HistorySource, MainConfig
from proxies import reddit_proxy
from services import config_service
from services import cover_service
from services import history_service
from services import speech_service
from services import video_service
import sys


def generate_cover(config: MainConfig):
    history = history_service.load_history(config.history_config)
    cover_service.__generate_html_cover(history.title, "cover.png", config.cover_config)


def generate_reddit_history(config: MainConfig):
    reddit_post = reddit_proxy.get_reddit_post(config.history_config.reddit_url)
    history = history_service.generate_history_from_reddit(reddit_post)
    cover = cover_service.generate_cover(
        history.title,
        config.cover_config,
    )
    print("Generating cover...")
    cover = cover_service.generate_cover(
        history.title,
        config.cover_config,
    )
    print("Generating speech...")
    speech = speech_service.synthesize_speech(
        history.title + "\n\n" + history.content,
    )
    print("Generating video compilation...")
    background_video = video_service.create_video_compilation(
        speech.clip.duration,
        config.video_config,
    )

    final_video = video_service.generate_video(
        audio=speech,
        background_video=background_video,
        cover=cover,
        config=config.video_config,
    )
    file_name = f"{config.output_path}/{history.file_name}.mp4"
    if config.video_config.low_quality:
        final_video.clip.write_videofile(
            file_name,
            threads=16,
            preset="ultrafast",
            fps=15,
        )
    else:
        final_video.clip.write_videofile(
            file_name,
            threads=16,
        )


def generate_history(config: MainConfig):
    print("Generating history...")
    history = history_service.load_history(config.history_config)
    history_service.save_history(
        history, f"{config.output_path}/{history.file_name}.yaml"
    )
    print("Generating cover...")
    cover = cover_service.generate_cover(
        history.title,
        config.cover_config,
    )
    print("Generating speech...")
    speech = speech_service.synthesize_speech(
        history.title + "\n\n" + history.content,
    )
    print("Generating video compilation...")
    background_video = video_service.create_video_compilation(
        speech.clip.duration,
        config.video_config,
    )

    final_video = video_service.generate_video(
        audio=speech,
        background_video=background_video,
        cover=cover,
        config=config.video_config,
    )
    file_name = f"{config.output_path}/{history.file_name}.mp4"
    if config.video_config.low_quality:
        final_video.clip.write_videofile(
            file_name,
            threads=16,
            preset="ultrafast",
            fps=15,
        )
    else:
        final_video.clip.write_videofile(
            file_name,
            threads=16,
        )


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = config_service.get_main_config(config_path)
    random.seed(config.int_seed())
    print("Seed:", config.seed)

    if config.history_config.source == HistorySource.REDDIT:
        generate_reddit_history(config)
    else:
        generate_history(config)
    # generate_cover(config_path)
