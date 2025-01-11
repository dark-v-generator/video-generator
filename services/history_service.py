from entities import config
from entities.history import History
from entities.reddit import RedditPost
from proxies import reddit_proxy
import proxies.open_api_proxy as open_api_proxy
import yaml


def load_history(cfg: config.HistoryConfig = config.HistoryConfig()) -> History:
    if cfg.source == config.HistorySource.CHAT_GPT:
        print("Auto generating history...")
        return open_api_proxy.generate_history(cfg.prompt)
    elif cfg.source == config.HistorySource.CONFIG:
        print("Loading history...")
        return History(
            title=cfg.title,
            content=cfg.content,
            file_name=cfg.file_name,
        )


def save_history(history: History, output_path: str):
    with open(output_path, "w") as file:
        yaml.dump(history.model_dump(), file, allow_unicode=True, width=100, indent=4)


def generate_history_from_reddit(reddit_post: RedditPost) -> History:
    history = open_api_proxy.convert_reddit_post_to_history(reddit_post)
    return (history, reddit_post)
