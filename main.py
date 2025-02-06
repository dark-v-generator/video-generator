import random
from entities.config import MainConfig
from services import config_service
from services import history_service
from services import video_service
from services import cover_service
import sys


def test_cover(cfg: MainConfig):
    histories = history_service.load_histories(cfg)
    for history in histories:
        cover_service.__generate_reddit_cover(
            history.title,
            history.reddit_community,
            history.reddit_post_author,
            history.reddit_community_url_photo,
            f"{history.file_name}.png",
            cfg.cover_config,
        )


if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = config_service.get_main_config(config_path)
    random.seed(config.int_seed())
    print("Seed:", config.seed)
    
    # test_cover(config)

    histories = history_service.load_histories(config)
    for history in histories:
        video_service.generate_history_video(history, config)
