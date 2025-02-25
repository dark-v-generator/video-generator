from src.entities.reddit_history import RedditHistory
from src.services import config_service, history_service

config = config_service.get_main_config()
history_id = "39fd751a-a0ac-49d4-bfae-b846d1cb6a72"
reddit_history: RedditHistory = history_service.get_reddit_history(history_id, config)
history_service.generate_reddit_video(reddit_history, config)