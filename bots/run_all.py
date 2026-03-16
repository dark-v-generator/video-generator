"""Launch both Telegram bots in parallel."""

import multiprocessing
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def run_image_story_bot():
    from bots.image_story_bot import main
    main()


def run_two_part_history_bot():
    from bots.two_part_history_bot import main
    main()


if __name__ == "__main__":
    processes = []

    logger.info("Starting Telegram bots...")

    p1 = multiprocessing.Process(target=run_image_story_bot, name="image-story-bot")
    p2 = multiprocessing.Process(target=run_two_part_history_bot, name="two-part-history-bot")

    p1.start()
    p2.start()
    processes.extend([p1, p2])

    logger.info("Both bots are running. Press Ctrl+C to stop.")

    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        logger.info("Shutting down bots...")
        for p in processes:
            p.terminate()
        for p in processes:
            p.join(timeout=5)
