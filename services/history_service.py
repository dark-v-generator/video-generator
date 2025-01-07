import json
from entities import config
from entities.history import History
import proxies.open_api_proxy as open_api_proxy


def generate_history(config: config.HistoryConfig = config.HistoryConfig()) -> History:
    if config.use_file:
        with open(config.history_path, "r") as file:
            data = json.load(file)
            return History(**data)
    return open_api_proxy.generate_history(config.prompt)


def save_history(history: History, output_path: str):
    with open(output_path, "w") as file:
        json.dump(history.dict(), file, indent=4)
