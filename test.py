

from src.entities.reddit_history import RedditHistory
from src.services import config_service, history_service

config = config_service.get_main_config()
history_id='8d898bec-8374-4074-a292-da9475447449'
reddit_history: RedditHistory = history_service.get_reddit_history(history_id, config)
new_histories = history_service.divide_reddit_history(reddit_history, config, 2)
for rhistory in new_histories:
    history=rhistory.history
    print(history.title)
    print(history.content)