from entities.captions import Captions
from proxies import open_api_proxy
from services import config_service, history_service


config = config_service.get_main_config("config.yaml")
history_id = '440ef369-a1c8-4e48-baf3-325d903960be'

reddit_history = history_service.get_reddit_history(history_id, config=config)
captions = Captions.from_yaml(reddit_history.captions_path).stripped()
captions.save_yaml('original_captions.yaml')
new_captions = open_api_proxy.enhance_captions(captions, reddit_history.history)
new_captions.save_yaml('new_captions.yaml')