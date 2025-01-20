from typing import List
from entities import config
from entities.history import History
from entities.reddit import RedditPost
from proxies import reddit_proxy
import proxies.open_api_proxy as open_api_proxy
import yaml

def __generate_histories_from_reddit(reddit_post: RedditPost) -> History:
    return open_api_proxy.convert_reddit_post_to_history(reddit_post)

def __generate_histories_from_reddit(reddit_post: RedditPost, cfg: config.HistoryConfig) -> List[History]:
    if cfg.number_of_parts == 1:
        return [open_api_proxy.convert_reddit_post_to_history(reddit_post)]
    else:
        multiple_part_history = open_api_proxy.convert_reddit_post_to_multiple_part_history(
            reddit_post=reddit_post, 
            number_of_parts=cfg.number_of_parts
        )
        return multiple_part_history.get_histories()

def __load_histories_from_config(cfg: config.HistoryConfig) -> List[History]:
    histories = []
    for data in cfg.histories:
        return [History(**data.model_dump())]
    return histories

def load_history(cfg: config.MainConfig = config.MainConfig()) -> List[History]:
    if cfg.history_config.source == config.HistorySource.CONFIG:
        return __load_histories_from_config(cfg.history_config)
    elif cfg.history_config.source == config.HistorySource.REDDIT:
        reddit_post = reddit_proxy.get_reddit_post(cfg.history_config.reddit_url)
        histories =  __generate_histories_from_reddit(reddit_post, cfg.history_config)
        __save_histories(
            histories, f"{cfg.output_path}/{reddit_post.title.lower().replace(' ', '_')}.yaml"
        )
        return histories

def __save_histories(histories: List[History], output_path: str):
    data = { 'histories': [] }
    for history in histories:
        data['histories'].append(history.model_dump())
    with open(output_path, "w") as file:
        yaml.dump(data, file, allow_unicode=True, width=100, indent=4)
