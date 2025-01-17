import random
from services import config_service
from services import history_service
from services import video_service
from services import cover_service
import sys


def test_cover():
    config = config_service.get_main_config("config.yaml")
    history = history_service.load_history(config)
    cover_service.__generate_reddit_cover(
        history.title,
        history.reddit_community,
        history.reddit_post_author,
        history.reddit_community_url_photo,
        "output.png",
        config.cover_config,
    )


if __name__ == "__main__":
    # test_cover()
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = config_service.get_main_config(config_path)
    random.seed(config.int_seed())
    print("Seed:", config.seed)

    history = history_service.load_history(config)
    history_service.save_history(
        history, f"{config.output_path}/{history.file_name}.yaml"
    )
    video_service.generate_history_video(history, config)
