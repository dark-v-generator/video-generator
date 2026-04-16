"""Interactive Telegram bot with checkpoint flow for image-story video generation.

Flow: /generate <url> -> scrape -> script review -> audio review -> images review -> video review.
At each checkpoint the user can approve or request changes.
"""

import logging
import os
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bots.base import (
    is_user_allowed,
    reject_unauthorized,
    send_audio_bytes,
    send_image_bytes,
    send_video_bytes,
)
from src.core.container import container
from src.core.secrets import secrets
from src.entities.config import MainConfig
from src.services.reddit_video_service import RedditVideoService

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.yaml")
config = MainConfig.from_yaml(CONFIG_PATH)
bot_config = config.bots.image_story_bot

REVIEW_SCRIPT, REVIEW_AUDIO, REVIEW_IMAGES, REVIEW_VIDEO = range(4)

APPROVE_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("Approve", callback_data="approve")]]
)


def _get_service() -> RedditVideoService:
    container.wire(modules=[__name__])
    return container.reddit_video_service()


OUTPUT_DIR = Path("output")


def _truncate(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _save_video(video_bytes: bytes, name: str) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / name
    path.write_bytes(video_bytes)
    logger.info("Saved %s (%.1f MB)", path, len(video_bytes) / (1024 * 1024))
    return path


# ---------------------------------------------------------------------------
# /start
# ---------------------------------------------------------------------------


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_user_allowed(update.effective_user.id, bot_config.allowed_user_ids):
        await reject_unauthorized(update)
        return
    await update.message.reply_text(
        "Send /generate <reddit-url> to start creating a video.\n"
        "At each step you can approve or request changes."
    )


# ---------------------------------------------------------------------------
# /generate — entry point
# ---------------------------------------------------------------------------


async def cmd_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_user_allowed(update.effective_user.id, bot_config.allowed_user_ids):
        await reject_unauthorized(update)
        return ConversationHandler.END

    args = context.args
    if not args:
        await update.message.reply_text("Usage: /generate <reddit-url>")
        return ConversationHandler.END

    url = args[0]
    if "reddit.com" not in url:
        await update.message.reply_text("Please provide a valid Reddit URL.")
        return ConversationHandler.END

    await update.message.reply_text("Scraping post and generating script...")

    try:
        service = _get_service()
        post = service.scrape_post(url)
        script = await service.generate_script(post)

        context.user_data["service"] = service
        context.user_data["post"] = post
        context.user_data["script"] = script

        await _send_script_preview(update, script)
        return REVIEW_SCRIPT

    except Exception as e:
        logger.exception("Failed during scrape/script generation")
        await update.message.reply_text(f"Error: {e}")
        return ConversationHandler.END


# ---------------------------------------------------------------------------
# REVIEW_SCRIPT state
# ---------------------------------------------------------------------------


async def _send_script_preview(update: Update, script) -> None:
    header = f"*{script.title}*\nNarrator: {script.resolved_gender}\n\n"
    part1_preview = f"**Part 1**\n{_truncate(script.part1, 1800)}\n\n"
    part2_preview = f"**Part 2**\n{_truncate(script.part2, 1800)}"
    text = header + part1_preview + part2_preview

    target = update.callback_query.message if update.callback_query else update.message
    await target.reply_text(
        text,
        reply_markup=APPROVE_KEYBOARD,
    )


async def on_script_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Generating audio... this may take a minute.")

    try:
        service: RedditVideoService = context.user_data["service"]
        script = context.user_data["script"]

        audio = await service.generate_audio(script)
        context.user_data["audio"] = audio

        await send_audio_bytes(query.message, audio.part1.bytes, "Part 1 audio")
        await send_audio_bytes(query.message, audio.part2.bytes, "Part 2 audio")
        await query.message.reply_text(
            "Audio generated. Approve or send a message to request changes "
            "(e.g. 'slower', 'female voice').",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_AUDIO

    except Exception as e:
        logger.exception("Failed during audio generation")
        await query.message.reply_text(f"Error: {e}")
        return ConversationHandler.END


async def on_script_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    feedback = update.message.text
    await update.message.reply_text("Revising script...")

    try:
        service: RedditVideoService = context.user_data["service"]
        script = context.user_data["script"]
        revised = await service.revise_script(script, feedback)
        context.user_data["script"] = revised

        await _send_script_preview(update, revised)
        return REVIEW_SCRIPT

    except Exception as e:
        logger.exception("Failed during script revision")
        await update.message.reply_text(f"Error: {e}")
        return REVIEW_SCRIPT


# ---------------------------------------------------------------------------
# REVIEW_AUDIO state
# ---------------------------------------------------------------------------


async def on_audio_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Generating captions and AI images... this will take a few minutes."
    )

    try:
        service: RedditVideoService = context.user_data["service"]
        script = context.user_data["script"]
        audio = context.user_data["audio"]

        captions = await service.generate_captions_pair(audio, script)
        context.user_data["captions"] = captions

        image_stories = await service.generate_image_stories(script, captions)
        context.user_data["image_stories"] = image_stories

        await _send_images_preview(query.message, image_stories)
        total = len(image_stories.generated_images_1) + len(
            image_stories.generated_images_2
        )
        await query.message.reply_text(
            f"{total} images generated (preview above shows a sample). "
            "All images will be used in the final video.\n\n"
            "Approve or send 'regenerate' to get new images.",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_IMAGES

    except Exception as e:
        logger.exception("Failed during image generation")
        await query.message.reply_text(f"Error: {e}")
        return ConversationHandler.END


async def on_audio_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    feedback = update.message.text.lower()
    await update.message.reply_text("Re-generating audio with your changes...")

    try:
        service: RedditVideoService = context.user_data["service"]
        script = context.user_data["script"]

        rate = 1.0
        if "slower" in feedback:
            rate = 0.85
        elif "faster" in feedback:
            rate = 1.15

        if "female" in feedback:
            script.resolved_gender = "female"
        elif "male" in feedback:
            script.resolved_gender = "male"

        audio = await service.generate_audio(script, speech_rate=rate)
        context.user_data["audio"] = audio

        await send_audio_bytes(
            update.message, audio.part1.bytes, "Part 1 audio (revised)"
        )
        await send_audio_bytes(
            update.message, audio.part2.bytes, "Part 2 audio (revised)"
        )
        await update.message.reply_text(
            "Revised audio ready. Approve or request more changes.",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_AUDIO

    except Exception as e:
        logger.exception("Failed during audio re-generation")
        await update.message.reply_text(f"Error: {e}")
        return REVIEW_AUDIO


# ---------------------------------------------------------------------------
# REVIEW_IMAGES state
# ---------------------------------------------------------------------------


async def _send_images_preview(message, image_stories) -> None:
    """Send a sample of generated images (up to 3 per part) for user review."""
    for label, images in [
        ("Part 1", image_stories.generated_images_1),
        ("Part 2", image_stories.generated_images_2),
    ]:
        samples = images[:3]
        for i, img_bytes in enumerate(samples, 1):
            await send_image_bytes(
                message, img_bytes, f"{label} — image {i}/{len(images)}"
            )


async def on_images_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Generating cover and composing video... this will take a few minutes."
    )

    try:
        service: RedditVideoService = context.user_data["service"]
        audio = context.user_data["audio"]
        captions = context.user_data["captions"]
        image_stories = context.user_data["image_stories"]
        post = context.user_data["post"]
        script = context.user_data["script"]

        cover1, cover2 = await service.generate_cover_pair(post, script)
        context.user_data["cover1"] = cover1
        context.user_data["cover2"] = cover2

        videos = service.compose_image_story_video(
            audio,
            captions,
            image_stories,
            cover1,
            cover2,
            low_quality=bot_config.low_quality,
        )
        context.user_data["videos"] = videos

        _save_video(videos.part1_video, "part1.mp4")
        _save_video(videos.part2_video, "part2.mp4")

        await send_video_bytes(query.message, videos.part1_video, "Part 1")
        await send_video_bytes(query.message, videos.part2_video, "Part 2")
        await query.message.reply_text(
            "Videos generated. Approve to finish, or send a message to request changes.",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_VIDEO

    except Exception as e:
        logger.exception("Failed during video composition")
        await query.message.reply_text(f"Error: {e}")
        return ConversationHandler.END


async def on_images_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Regenerating AI images... this will take a few minutes."
    )

    try:
        service: RedditVideoService = context.user_data["service"]
        script = context.user_data["script"]
        captions = context.user_data["captions"]

        image_stories = await service.generate_image_stories(script, captions)
        context.user_data["image_stories"] = image_stories

        await _send_images_preview(update.message, image_stories)
        await update.message.reply_text(
            "New images generated. Approve or send 'regenerate' again.",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_IMAGES

    except Exception as e:
        logger.exception("Failed during image regeneration")
        await update.message.reply_text(f"Error: {e}")
        return REVIEW_IMAGES


# ---------------------------------------------------------------------------
# REVIEW_VIDEO state
# ---------------------------------------------------------------------------


async def on_video_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("All done! Send /generate to start another.")
    context.user_data.clear()
    return ConversationHandler.END


async def on_video_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Re-composing video... this will take a few minutes."
    )

    try:
        service: RedditVideoService = context.user_data["service"]
        audio = context.user_data["audio"]
        captions = context.user_data["captions"]
        image_stories = context.user_data["image_stories"]
        cover1 = context.user_data["cover1"]
        cover2 = context.user_data["cover2"]

        videos = service.compose_image_story_video(
            audio,
            captions,
            image_stories,
            cover1,
            cover2,
            low_quality=bot_config.low_quality,
        )
        context.user_data["videos"] = videos

        _save_video(videos.part1_video, "part1.mp4")
        _save_video(videos.part2_video, "part2.mp4")

        await send_video_bytes(update.message, videos.part1_video, "Part 1 (revised)")
        await send_video_bytes(update.message, videos.part2_video, "Part 2 (revised)")
        await update.message.reply_text(
            "Revised videos ready. Approve or request more changes.",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_VIDEO

    except Exception as e:
        logger.exception("Failed during video re-composition")
        await update.message.reply_text(f"Error: {e}")
        return REVIEW_VIDEO


# ---------------------------------------------------------------------------
# /cancel
# ---------------------------------------------------------------------------


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelled. Send /generate to start over.")
    context.user_data.clear()
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    token = secrets.telegram_image_story_bot_token
    if not token:
        raise RuntimeError("TELEGRAM_IMAGE_STORY_BOT_TOKEN env var is not set")

    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("generate", cmd_generate)],
        states={
            REVIEW_SCRIPT: [
                CallbackQueryHandler(on_script_approve, pattern="^approve$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_script_change),
            ],
            REVIEW_AUDIO: [
                CallbackQueryHandler(on_audio_approve, pattern="^approve$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_audio_change),
            ],
            REVIEW_IMAGES: [
                CallbackQueryHandler(on_images_approve, pattern="^approve$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_images_change),
            ],
            REVIEW_VIDEO: [
                CallbackQueryHandler(on_video_approve, pattern="^approve$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_video_change),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_user=True,
        per_chat=True,
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("start", cmd_start))

    logger.info("Interactive bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
