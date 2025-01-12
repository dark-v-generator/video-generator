import random
from entities.config import HistorySource, MainConfig
from entities.reddit import RedditPost
from proxies import reddit_proxy
from services import config_service
from services import cover_service
from services import history_service
from services import speech_service
from services import video_service
import sys

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = config_service.get_main_config(config_path)
    random.seed(config.int_seed())
    # cover_service.__generate_html_cover(history.title, "cover.png", config.cover_config)
    cover_service.__generate_reddit_cover(
        "husbands mistress was rude to me, so i ruined her favourite thing, twice",
        reddit_post=RedditPost(
            community_url_photo="https://styles.redditmedia.com/t5_2vg7t/styles/communityIcon_6ofkqruptzc71.png",
            author="nelinthemirror",
            community="pettyrevenge",
        ),
        output_path="reddit_cover.png",
        config=config.cover_config,
    )
