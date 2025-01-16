from entities import config
from entities.history import History
from entities.reddit import RedditPost
from proxies import reddit_proxy
import proxies.open_api_proxy as open_api_proxy
import yaml

def __generate_history_from_reddit(reddit_post: RedditPost) -> History:
    return open_api_proxy.convert_reddit_post_to_history(reddit_post)

def __generate_history_from_reddit(reddit_post: RedditPost) -> History:
    return open_api_proxy.convert_reddit_post_to_history(reddit_post)


def load_history(cfg: config.MainConfig = config.MainConfig()) -> History:
    if cfg.history_config.source == config.HistorySource.CHAT_GPT:
        print("Auto generating history...")
        return open_api_proxy.generate_history(cfg.history_config.prompt)
    elif cfg.history_config.source == config.HistorySource.CONFIG:
        print("Loading history...")
        return History(**cfg.model_dump())
    elif cfg.history_config.source == config.HistorySource.REDDIT:
        reddit_post = reddit_proxy.get_reddit_post(cfg.history_config.reddit_url)
        return __generate_history_from_reddit(reddit_post)

def save_history(history: History, output_path: str):
    with open(output_path, "w") as file:
        yaml.dump(history.model_dump(), file, allow_unicode=True, width=100, indent=4)
