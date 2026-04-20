"""Telegram bot que gera vídeos com fundo satisfatório a partir de URLs do Reddit
e opcionalmente faz upload no TikTok (imediato ou agendado)."""

import asyncio
import datetime
import logging
import os
import re
import tempfile

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

from src.core.container import container
from src.core.secrets import secrets
from src.entities.config import MainConfig
from src.entities.language import Language

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
        await asyncio.to_thread(
            tiktok_proxy.upload_video,
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


FIND_CALLBACK_PREFIX = "fg:"
_find_url_store: dict[str, str] = {}
_find_url_counter = 0

LLM_LABELS = {
    "retencao": "Retenção",
    "qualidade": "Qualidade",
    "viralizacao": "Viralização",
    "adequacao_tiktok": "TikTok Fit",
    "gancho": "Gancho",
}


def _store_url(url: str) -> str:
    global _find_url_counter
    _find_url_counter += 1
    key = str(_find_url_counter)
    _find_url_store[key] = url
    return key


def _format_bar(value: float, width: int = 10) -> str:
    filled = round(value / 100 * width)
    return "▓" * filled + "░" * (width - filled)


async def cmd_find(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_allowed(user_id, bot_config.allowed_user_ids):
        await reject_unauthorized(update)
        return

    await update.message.reply_text(
        "Buscando as melhores histórias do dia... pode demorar um pouco."
    )

    try:
        container.wire(modules=[__name__])
        finder = container.story_finder_service()

        results = await finder.find_best_stories(
            sort="top",
            time_filter="day",
            top_per_sub=2,
            language=Language.PORTUGUESE,
        )
    except Exception as e:
        logger.exception("Failed to find stories")
        await update.message.reply_text(f"Erro ao buscar histórias: {e}")
        return

    if not results:
        await update.message.reply_text("Nenhuma história boa encontrada hoje.")
        return

    for i, story in enumerate(results):
        post = story.post
        notas = story.evaluation.get("notas", {})
        sub = post.community.replace("r/", "")

        lines = [
            f"#{i + 1} [{story.veredito}] — {story.nota_geral}/100",
            f"r/{sub} | {post.score or 0} pts | {post.num_comments or 0} comments",
            "",
        ]

        for key, label in LLM_LABELS.items():
            entry = notas.get(key, {})
            nota = entry.get("nota", 0)
            lines.append(f"  {label}: {_format_bar(nota)} {nota}")

        lines.append("")
        lines.append(f"{story.resumo[:400]}")

        text = "\n".join(lines)
        url_key = _store_url(post.url)

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "🎬 Gerar Vídeo",
                callback_data=f"{FIND_CALLBACK_PREFIX}{url_key}",
            )]
        ])

        await update.message.reply_text(text, reply_markup=keyboard)

    await update.message.reply_text(
        f"{len(results)} histórias encontradas. Clique em 'Gerar Vídeo' pra criar."
    )


TIKTOK_PREFIX = "tt:"

SCHEDULE_SLOTS = {
    "now": ("🚀 Agora", None),
    "h_m": ("☀️ Hoje Manhã", 9),
    "h_t": ("🌤 Hoje Tarde", 14),
    "h_n": ("🌙 Hoje Noite", 20),
    "a_m": ("☀️ Amanhã Manhã", 9),
    "a_t": ("🌤 Amanhã Tarde", 14),
    "a_n": ("🌙 Amanhã Noite", 20),
    "skip": ("⏭ Pular", None),
}


def _build_schedule_dt(slot: str) -> datetime.datetime | None:
    """Build a UTC datetime for the given slot, or None for 'now'."""
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    if slot.startswith("h_"):
        day = now
    elif slot.startswith("a_"):
        day = now + datetime.timedelta(days=1)
    else:
        return None

    hour = SCHEDULE_SLOTS[slot][1]
    scheduled = day.replace(hour=hour, minute=0, second=0, microsecond=0)

    if scheduled <= now + datetime.timedelta(minutes=MIN_SCHEDULE_MINUTES):
        return None

    return scheduled


def _build_tiktok_keyboard(vid_key: str) -> InlineKeyboardMarkup:
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    rows = []

    row_now = [InlineKeyboardButton("🚀 Agora", callback_data=f"{TIKTOK_PREFIX}{vid_key}:now")]
    rows.append(row_now)

    today_buttons = []
    for slot in ("h_m", "h_t", "h_n"):
        label = SCHEDULE_SLOTS[slot][0]
        hour = SCHEDULE_SLOTS[slot][1]
        candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate > now + datetime.timedelta(minutes=MIN_SCHEDULE_MINUTES):
            today_buttons.append(
                InlineKeyboardButton(label, callback_data=f"{TIKTOK_PREFIX}{vid_key}:{slot}")
            )
    if today_buttons:
        rows.append(today_buttons)

    tomorrow_buttons = []
    for slot in ("a_m", "a_t", "a_n"):
        label = SCHEDULE_SLOTS[slot][0]
        tomorrow_buttons.append(
            InlineKeyboardButton(label, callback_data=f"{TIKTOK_PREFIX}{vid_key}:{slot}")
        )
    rows.append(tomorrow_buttons)

    rows.append([InlineKeyboardButton("⏭ Pular", callback_data=f"{TIKTOK_PREFIX}{vid_key}:skip")])

    return InlineKeyboardMarkup(rows)


async def handle_find_generate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_user_allowed(user_id, bot_config.allowed_user_ids):
        await query.message.reply_text("Sem permissão.")
        return

    url_key = query.data.removeprefix(FIND_CALLBACK_PREFIX)
    url = _find_url_store.get(url_key)
    if not url:
        await query.message.reply_text("Link expirado. Rode /find de novo.")
        return

    await query.edit_message_reply_markup(reply_markup=None)
    status_msg = await query.message.reply_text("⏳ Gerando vídeo... pode demorar alguns minutos.")

    try:
        container.wire(modules=[__name__])
        service = container.reddit_video_service()

        result = await service.generate_satisfying_video(
            post_url=url,
            low_quality=bot_config.low_quality,
        )

        await status_msg.edit_text("📤 Enviando áudio...")
        await send_audio_bytes(query.message, result.audio, "Narração")

        video_mb = len(result.video) / (1024 * 1024)
        if video_mb > 49:
            await status_msg.edit_text(
                f"📤 Comprimindo vídeo ({video_mb:.0f} MB)... pode demorar."
            )
        else:
            await status_msg.edit_text("📤 Enviando vídeo...")
        await send_video_bytes(query.message, result.video, "Vídeo pronto")

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.write(result.video)
        tmp.close()

        title = result.story_md.split("\n")[0].lstrip("# ").strip()
        vid_key = _store_url(tmp.name)
        _find_url_store[f"title:{vid_key}"] = title

        keyboard = _build_tiktok_keyboard(vid_key)

        await status_msg.edit_text("✅ Vídeo pronto!")
        await query.message.reply_text("Subir no TikTok?", reply_markup=keyboard)

    except Exception as e:
        logger.exception("Failed to generate video from /find")
        await status_msg.edit_text(f"❌ Erro ao gerar vídeo: {e}")


async def handle_tiktok_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    payload = query.data.removeprefix(TIKTOK_PREFIX)
    vid_key, slot = payload.rsplit(":", 1)

    video_path = _find_url_store.get(vid_key)
    title = _find_url_store.get(f"title:{vid_key}", "")

    if slot == "skip":
        _cleanup_temp(video_path)
        await query.edit_message_text("Upload pulado.")
        return

    if not video_path or not os.path.exists(video_path):
        await query.edit_message_text("Arquivo do vídeo não encontrado.")
        return

    schedule = _build_schedule_dt(slot) if slot != "now" else None

    if slot != "now" and schedule is None:
        await query.edit_message_text("Horário já passou. Escolha outro.")
        return

    label = "agora" if not schedule else schedule.strftime("%d/%m %H:%M UTC")
    await query.edit_message_text(f"Subindo no TikTok ({label})...")

    try:
        tiktok_proxy = container.tiktok_proxy()
        description = f"{title} #reddit #história #storytelling #fyp"
        await asyncio.to_thread(
            tiktok_proxy.upload_video,
            video_path=video_path,
            description=description,
            schedule=schedule,
        )
        await query.message.reply_text(f"Upload pro TikTok concluído! ({label})")
    except Exception as e:
        logger.exception("Failed to upload to TikTok")
        await query.message.reply_text(f"Falha no upload: {e}")
    finally:
        _cleanup_temp(video_path)


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
    app.add_handler(CommandHandler("find", cmd_find))
    app.add_handler(CallbackQueryHandler(handle_find_generate, pattern=f"^{FIND_CALLBACK_PREFIX}"))
    app.add_handler(CallbackQueryHandler(handle_tiktok_action, pattern=f"^{TIKTOK_PREFIX}"))

    logger.info("Satisfying video bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
