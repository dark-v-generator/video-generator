"""Launch both Telegram bots in parallel."""

import multiprocessing
import logging

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def run_interactive_bot():
    from bots.interactive_bot import main
    main()


def run_satisfying_bot():
    from bots.satisfying_bot import main
    main()


if __name__ == "__main__":
    processes = []

    logger.info("Starting Telegram bots...")

    p1 = multiprocessing.Process(target=run_interactive_bot, name="interactive-bot")
    p2 = multiprocessing.Process(target=run_satisfying_bot, name="satisfying-bot")

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
