import random
from services import config_service
from services import history_service
from services import video_service
import sys

if __name__ == "__main__":
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config.yaml"
    config = config_service.get_main_config(config_path)
    random.seed(config.int_seed())
    print("Seed:", config.seed)

    history = history_service.load_history(config)
    history_service.save_history(
        history, f"{config.output_path}/{history.file_name}.yaml"
    )
    video_service.generate_history_video(history, config)
