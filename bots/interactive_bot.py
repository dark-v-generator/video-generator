"""Bot interativo do Telegram com fluxo de checkpoints para geração de vídeos com imagens IA.

Fluxo: /generate <url> -> scrape -> roteiro (auto) -> áudio -> revisão de imagens -> vídeo.
O roteiro é aprovado automaticamente. A partir do áudio o usuário pode aprovar ou pedir mudanças.
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

REVIEW_AUDIO, REVIEW_IMAGES, REVIEW_VIDEO = range(3)

APPROVE_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("Aprovar", callback_data="approve")]]
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
        "Manda /generate <url-do-reddit> pra começar a criar um vídeo.\n"
        "Em cada etapa você pode aprovar ou pedir mudanças."
    )


# ---------------------------------------------------------------------------
# /generate — entry point (scrape + script auto-approved + audio)
# ---------------------------------------------------------------------------


async def cmd_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_user_allowed(update.effective_user.id, bot_config.allowed_user_ids):
        await reject_unauthorized(update)
        return ConversationHandler.END

    args = context.args
    if not args:
        await update.message.reply_text("Uso: /generate <url-do-reddit>")
        return ConversationHandler.END

    url = args[0]
    if "reddit.com" not in url:
        await update.message.reply_text("Manda um link válido do Reddit.")
        return ConversationHandler.END

    await update.message.reply_text("Buscando post e gerando roteiro...")

    try:
        service = _get_service()
        post = service.scrape_post(url)
        script = await service.generate_script(post)

        context.user_data["service"] = service
        context.user_data["post"] = post
        context.user_data["script"] = script

        header = f"*{script.title}*\nNarrador: {script.resolved_gender}\n\n"
        part1_preview = f"**Parte 1**\n{_truncate(script.part1, 1800)}\n\n"
        part2_preview = f"**Parte 2**\n{_truncate(script.part2, 1800)}"
        await update.message.reply_text(header + part1_preview + part2_preview)

        await update.message.reply_text("Gerando áudio...")

        audio = await service.generate_audio(script)
        context.user_data["audio"] = audio

        await send_audio_bytes(update.message, audio.part1.bytes, "Áudio Parte 1")
        await send_audio_bytes(update.message, audio.part2.bytes, "Áudio Parte 2")
        await update.message.reply_text(
            "Áudio gerado. Aprova ou manda uma mensagem pra pedir mudanças "
            "(ex: 'mais devagar', 'voz feminina').",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_AUDIO

    except Exception as e:
        logger.exception("Failed during scrape/script/audio generation")
        await update.message.reply_text(f"Erro: {e}")
        return ConversationHandler.END


# ---------------------------------------------------------------------------
# REVIEW_AUDIO state
# ---------------------------------------------------------------------------


async def on_audio_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Gerando legendas e imagens... pode demorar alguns minutos."
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
            f"{total} imagens geradas (acima uma amostra). "
            "Todas serão usadas no vídeo final.\n\n"
            "Aprova ou manda 'regenerar' pra gerar novas imagens.",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_IMAGES

    except Exception as e:
        logger.exception("Failed during image generation")
        await query.message.reply_text(f"Erro: {e}")
        return ConversationHandler.END


async def on_audio_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    feedback = update.message.text.lower()
    await update.message.reply_text("Gerando áudio novamente com as mudanças...")

    try:
        service: RedditVideoService = context.user_data["service"]
        script = context.user_data["script"]

        rate = 1.0
        if "devagar" in feedback or "slower" in feedback:
            rate = 0.85
        elif "rápido" in feedback or "faster" in feedback:
            rate = 1.15

        if "feminina" in feedback or "female" in feedback:
            script.resolved_gender = "female"
        elif "masculina" in feedback or "male" in feedback:
            script.resolved_gender = "male"

        audio = await service.generate_audio(script, speech_rate=rate)
        context.user_data["audio"] = audio

        await send_audio_bytes(update.message, audio.part1.bytes, "Áudio Parte 1 (revisado)")
        await send_audio_bytes(update.message, audio.part2.bytes, "Áudio Parte 2 (revisado)")
        await update.message.reply_text(
            "Áudio revisado. Aprova ou pede mais mudanças.",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_AUDIO

    except Exception as e:
        logger.exception("Failed during audio re-generation")
        await update.message.reply_text(f"Erro: {e}")
        return REVIEW_AUDIO


# ---------------------------------------------------------------------------
# REVIEW_IMAGES state
# ---------------------------------------------------------------------------


async def _send_images_preview(message, image_stories) -> None:
    """Send a sample of generated images (up to 3 per part) for user review."""
    for label, images in [
        ("Parte 1", image_stories.generated_images_1),
        ("Parte 2", image_stories.generated_images_2),
    ]:
        samples = images[:3]
        for i, img_bytes in enumerate(samples, 1):
            await send_image_bytes(
                message, img_bytes, f"{label} — imagem {i}/{len(images)}"
            )


async def on_images_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        "Gerando capa e montando o vídeo... pode demorar alguns minutos."
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

        videos = await service.compose_image_story_video(
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

        await send_video_bytes(query.message, videos.part1_video, "Parte 1")
        await send_video_bytes(query.message, videos.part2_video, "Parte 2")
        await query.message.reply_text(
            "Vídeos gerados. Aprova pra finalizar ou manda uma mensagem pra pedir mudanças.",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_VIDEO

    except Exception as e:
        logger.exception("Failed during video composition")
        await query.message.reply_text(f"Erro: {e}")
        return ConversationHandler.END


async def on_images_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Regenerando imagens... pode demorar alguns minutos."
    )

    try:
        service: RedditVideoService = context.user_data["service"]
        script = context.user_data["script"]
        captions = context.user_data["captions"]

        image_stories = await service.generate_image_stories(script, captions)
        context.user_data["image_stories"] = image_stories

        await _send_images_preview(update.message, image_stories)
        await update.message.reply_text(
            "Novas imagens geradas. Aprova ou manda 'regenerar' de novo.",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_IMAGES

    except Exception as e:
        logger.exception("Failed during image regeneration")
        await update.message.reply_text(f"Erro: {e}")
        return REVIEW_IMAGES


# ---------------------------------------------------------------------------
# REVIEW_VIDEO state
# ---------------------------------------------------------------------------


async def on_video_approve(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("Pronto! Manda /generate pra criar outro.")
    context.user_data.clear()
    return ConversationHandler.END


async def on_video_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Remontando o vídeo... pode demorar alguns minutos."
    )

    try:
        service: RedditVideoService = context.user_data["service"]
        audio = context.user_data["audio"]
        captions = context.user_data["captions"]
        image_stories = context.user_data["image_stories"]
        cover1 = context.user_data["cover1"]
        cover2 = context.user_data["cover2"]

        videos = await service.compose_image_story_video(
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

        await send_video_bytes(update.message, videos.part1_video, "Parte 1 (revisado)")
        await send_video_bytes(update.message, videos.part2_video, "Parte 2 (revisado)")
        await update.message.reply_text(
            "Vídeos revisados. Aprova ou pede mais mudanças.",
            reply_markup=APPROVE_KEYBOARD,
        )
        return REVIEW_VIDEO

    except Exception as e:
        logger.exception("Failed during video re-composition")
        await update.message.reply_text(f"Erro: {e}")
        return REVIEW_VIDEO


# ---------------------------------------------------------------------------
# /cancel
# ---------------------------------------------------------------------------


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelado. Manda /generate pra começar de novo.")
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
