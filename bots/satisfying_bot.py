"""Telegram bot que gera vídeos com fundo satisfatório a partir de URLs do Reddit
e opcionalmente faz upload no TikTok (imediato ou agendado)."""

import datetime
import logging
import os
import re
import tempfile

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from src.core.container import container
from src.core.secrets import secrets
from src.entities.config import MainConfig

from bots.base import is_user_allowed, reject_unauthorized, send_audio_bytes, send_video_bytes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

config = MainConfig.from_yaml("config.yaml")
bot_config = config.bots.satisfying_bot

WAITING_URL, WAITING_UPLOAD_DECISION = range(2)

MIN_SCHEDULE_MINUTES = 20
MAX_SCHEDULE_DAYS = 10
SCHEDULE_RE = re.compile(r"^(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})$")


def _parse_schedule(text: str) -> datetime.datetime:
    """Parse 'DD/MM HH:MM' into a UTC datetime, validating constraints.

    Picks the nearest future occurrence of the given day/month/hour/minute,
    trying the current year first and rolling to the next year if needed.
    """
    m = SCHEDULE_RE.match(text.strip())
    if not m:
        raise ValueError(
            "Formato inválido. Use 'now' ou 'DD/MM HH:MM' (ex: 17/04 18:30)."
        )

    day, month = int(m.group(1)), int(m.group(2))
    hour, minute = int(m.group(3)), int(m.group(4))

    if not (1 <= month <= 12):
        raise ValueError("Mês inválido. Use um valor entre 01 e 12.")
    if not (0 <= hour <= 23):
        raise ValueError("Hora inválida. Use um valor entre 00 e 23.")
    if not (0 <= minute <= 59):
        raise ValueError("Minuto inválido. Use um valor entre 00 e 59.")

    now = datetime.datetime.now(tz=datetime.timezone.utc)

    scheduled = None
    for year in (now.year, now.year + 1):
        try:
            candidate = datetime.datetime(
                year, month, day, hour, minute,
                tzinfo=datetime.timezone.utc,
            )
        except ValueError:
            continue
        if candidate > now:
            scheduled = candidate
            break

    if scheduled is None:
        raise ValueError(
            f"Data inválida: {day:02d}/{month:02d} não existe ou já passou."
        )

    delta = scheduled - now
    if delta < datetime.timedelta(minutes=MIN_SCHEDULE_MINUTES):
        raise ValueError(
            f"O agendamento precisa ser no mínimo {MIN_SCHEDULE_MINUTES} minutos no futuro."
        )
    if delta > datetime.timedelta(days=MAX_SCHEDULE_DAYS):
        raise ValueError(
            f"O agendamento pode ser no máximo {MAX_SCHEDULE_DAYS} dias no futuro."
        )

    return scheduled


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_user_allowed(update.effective_user.id, bot_config.allowed_user_ids):
        await reject_unauthorized(update)
        return ConversationHandler.END
    await update.message.reply_text(
        "Me manda o link de um post do Reddit e eu gero um vídeo com fundo satisfatório."
    )
    return WAITING_URL


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if not is_user_allowed(user_id, bot_config.allowed_user_ids):
        await reject_unauthorized(update)
        return ConversationHandler.END

    url = update.message.text.strip()
    if "reddit.com" not in url:
        await update.message.reply_text("Manda um link válido do Reddit.")
        return WAITING_URL

    await update.message.reply_text("Gerando vídeo... pode demorar alguns minutos.")
    logger.info("User %s requested satisfying video for: %s", user_id, url)

    try:
        container.wire(modules=[__name__])
        service = container.reddit_video_service()

        result = await service.generate_satisfying_video(
            post_url=url,
            low_quality=bot_config.low_quality,
        )

        await send_audio_bytes(update.message, result.audio, "Narração")
        await send_video_bytes(update.message, result.video, "Vídeo pronto")

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(result.video)
        tmp.close()

        context.user_data["video_path"] = tmp.name
        context.user_data["video_title"] = result.story_md.split("\n")[0].lstrip("# ").strip()

        await update.message.reply_text(
            "Quer subir no TikTok?\n\n"
            "Manda 'now' pra subir agora,\n"
            "uma data tipo '17/04 18:30' (UTC) pra agendar,\n"
            "ou /skip pra pular."
        )
        return WAITING_UPLOAD_DECISION

    except Exception as e:
        logger.exception("Failed to generate video")
        await update.message.reply_text(f"Erro: {e}")
        return ConversationHandler.END


async def handle_upload_decision(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    video_path = context.user_data.get("video_path")
    title = context.user_data.get("video_title", "")

    if not video_path or not os.path.exists(video_path):
        await update.message.reply_text("Arquivo do vídeo não encontrado. Começa de novo.")
        return ConversationHandler.END

    try:
        schedule = None
        if text.lower() != "now":
            schedule = _parse_schedule(text)
    except ValueError as e:
        await update.message.reply_text(
            f"{e}\n\nTenta de novo: 'now', 'DD/MM HH:MM', ou /skip."
        )
        return WAITING_UPLOAD_DECISION

    action = f"agendado pra {schedule.strftime('%d/%m %H:%M')} UTC" if schedule else "agora"
    await update.message.reply_text(f"Subindo no TikTok ({action})...")

    try:
        tiktok_proxy = container.tiktok_proxy()
        description = f"{title} #reddit #história #storytelling #fyp"
        tiktok_proxy.upload_video(
            video_path=video_path,
            description=description,
            schedule=schedule,
        )
        await update.message.reply_text("Upload pro TikTok concluído!")
    except Exception as e:
        logger.exception("Failed to upload to TikTok")
        await update.message.reply_text(f"Falha no upload pro TikTok: {e}")
    finally:
        _cleanup_temp(video_path)
        context.user_data.clear()

    return ConversationHandler.END


async def skip_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    video_path = context.user_data.get("video_path")
    _cleanup_temp(video_path)
    context.user_data.clear()
    await update.message.reply_text("Upload pulado. Pronto!")
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    video_path = context.user_data.get("video_path")
    _cleanup_temp(video_path)
    context.user_data.clear()
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


def _cleanup_temp(path: str | None) -> None:
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def main() -> None:
    token = secrets.telegram_satisfying_bot_token
    if not token:
        raise RuntimeError("TELEGRAM_SATISFYING_BOT_TOKEN env var is not set")

    app = Application.builder().token(token).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url),
        ],
        states={
            WAITING_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url),
            ],
            WAITING_UPLOAD_DECISION: [
                CommandHandler("skip", skip_upload),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_upload_decision),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("skip", skip_upload),
        ],
    )

    app.add_handler(conv_handler)

    logger.info("Satisfying video bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
