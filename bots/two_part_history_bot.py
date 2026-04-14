"""Telegram bot that generates two-part YouTube-background videos from Reddit URLs."""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from src.core.container import container
from src.core.secrets import secrets
from src.entities.config import MainConfig

from bots.base import is_user_allowed, reject_unauthorized, send_video_bytes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

config = MainConfig.from_yaml("config.yaml")
bot_config = config.bots.two_part_history_bot


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_user_allowed(update.effective_user.id, bot_config.allowed_user_ids):
        await reject_unauthorized(update)
        return
    await update.message.reply_text(
        "Send me a Reddit post URL and I'll generate a two-part video with YouTube background."
    )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_allowed(user_id, bot_config.allowed_user_ids):
        await reject_unauthorized(update)
        return

    url = update.message.text.strip()
    if "reddit.com" not in url:
        await update.message.reply_text("Please send a valid Reddit post URL.")
        return

    await update.message.reply_text("Generating two-part video... This may take a few minutes.")
    logger.info("User %s requested two-part history for: %s", user_id, url)

    try:
        container.wire(modules=[__name__])
        service = container.reddit_video_service()

        result = await service.generate_two_part_history_video(
            post_url=url,
            low_quality=bot_config.low_quality,
        )

        await update.message.reply_text("Uploading Part 1...")
        await send_video_bytes(update.message, result.part1_video, "Part 1")

        await update.message.reply_text("Uploading Part 2...")
        await send_video_bytes(update.message, result.part2_video, "Part 2")

        await update.message.reply_text("Done!")

    except Exception as e:
        logger.exception("Failed to generate two-part video")
        await update.message.reply_text(f"Error: {e}")


def main() -> None:
    token = secrets.telegram_two_part_history_bot_token
    if not token:
        raise RuntimeError("TELEGRAM_TWO_PART_HISTORY_BOT_TOKEN env var is not set")

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    logger.info("Two-Part History bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
