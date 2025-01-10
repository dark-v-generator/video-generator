from entities import config
from entities.history import History
import proxies.open_api_proxy as open_api_proxy
import yaml


def load_history(config: config.HistoryConfig = config.HistoryConfig()) -> History:
    if config.auto_generate:
        print("Auto generating history...")
        return open_api_proxy.generate_history(config.prompt)
    else:
        print("Loading history...")
        return History(
            title=config.title,
            content=config.content,
            file_name=config.file_name,
        )

def save_history(history: History, output_path: str):
    with open(output_path, "w") as file:
        yaml.dump(history.model_dump(), file, allow_unicode=True, width=100, indent=4)
