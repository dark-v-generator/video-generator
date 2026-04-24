"""Telegram bot que gera vídeos com fundo satisfatório a partir de URLs do Reddit."""

import asyncio
import datetime
import logging
import os
from dataclasses import dataclass
from typing import Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Message, Update
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

from bots.base import (
    is_user_allowed,
    reject_unauthorized,
    send_audio_bytes,
    send_video_bytes,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

config = MainConfig.from_yaml("config.yaml")
bot_config = config.bots.satisfying_bot

WAITING_URL = 0


# ---------------------------------------------------------------------------
# Generation queue – processes video jobs sequentially so the bot stays
# responsive while heavy work runs in the background.
# ---------------------------------------------------------------------------

@dataclass
class _GenerationJob:
    url: str
    reply_message: Message
    status_message: Message


class GenerationQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[_GenerationJob] = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    @property
    def pending(self) -> int:
        return self._queue.qsize()

    @property
    def busy(self) -> bool:
        return self._running

    @property
    def position(self) -> int:
        """Position a newly enqueued job would have (1-based, counting the running job)."""
        return self.pending + (1 if self._running else 0) + 1

    async def enqueue(self, job: _GenerationJob) -> int:
        """Add a job and return its 1-based queue position."""
        pos = self.position
        await self._queue.put(job)
        return pos

    def start(self) -> None:
        if self._worker_task is None:
            self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self) -> None:
        logger.info("Generation queue worker started")
        while True:
            job = await self._queue.get()
            self._running = True
            try:
                await self._process(job)
            except Exception:
                logger.exception("Unhandled error in generation queue worker")
            finally:
                self._running = False
                self._queue.task_done()

    async def _process(self, job: _GenerationJob) -> None:
        try:
            await job.status_message.edit_text("⏳ Gerando vídeo...")

            container.wire(modules=[__name__])
            service = container.reddit_video_service()

            result = await service.generate_satisfying_video(
                post_url=job.url,
                low_quality=bot_config.low_quality,
            )

            await job.status_message.edit_text("📤 Enviando áudio...")
            await send_audio_bytes(job.reply_message, result.audio, "Narração")

            video_mb = len(result.video) / (1024 * 1024)
            if video_mb > 49:
                await job.status_message.edit_text(
                    f"📤 Comprimindo vídeo ({video_mb:.0f} MB)... pode demorar."
                )
            else:
                await job.status_message.edit_text("📤 Enviando vídeo...")
            await send_video_bytes(job.reply_message, result.video, "Vídeo pronto")

            await job.status_message.edit_text("✅ Vídeo pronto!")

        except Exception as e:
            logger.exception("Failed to generate video for %s", job.url)
            await job.status_message.edit_text(f"❌ Erro ao gerar vídeo: {e}")


generation_queue = GenerationQueue()


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

    logger.info("User %s requested satisfying video for: %s", user_id, url)
    status_msg = await update.message.reply_text("⏳ Adicionando à fila...")

    job = _GenerationJob(url=url, reply_message=update.message, status_message=status_msg)
    pos = await generation_queue.enqueue(job)

    if pos > 1:
        await status_msg.edit_text(f"🕐 Na fila — posição #{pos}. Aguarde...")
    else:
        await status_msg.edit_text("⏳ Gerando vídeo... pode demorar alguns minutos.")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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


async def _run_find(bot, chat_id: int) -> None:
    """Core /find logic: discover and rank stories, send results with generate buttons."""
    try:
        container.wire(modules=[__name__])
        finder = container.story_finder_service()

        results = await finder.find_best_stories(
            sort="top",
            time_filter="day",
            top_per_sub=5,
            language=Language.PORTUGUESE,
        )
    except Exception as e:
        logger.exception("Failed to find stories")
        await bot.send_message(chat_id, f"Erro ao buscar histórias: {e}")
        return

    if not results:
        await bot.send_message(chat_id, "Nenhuma história boa encontrada hoje.")
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

        await bot.send_message(chat_id, text, reply_markup=keyboard)

    await bot.send_message(
        chat_id,
        f"{len(results)} histórias encontradas. Clique em 'Gerar Vídeo' pra criar.",
    )


async def cmd_find(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_allowed(user_id, bot_config.allowed_user_ids):
        await reject_unauthorized(update)
        return

    await update.message.reply_text(
        "Buscando as melhores histórias do dia... pode demorar um pouco."
    )
    await _run_find(context.bot, update.effective_chat.id)


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
    status_msg = await query.message.reply_text("⏳ Adicionando à fila...")

    job = _GenerationJob(url=url, reply_message=query.message, status_message=status_msg)
    pos = await generation_queue.enqueue(job)

    if pos > 1:
        await status_msg.edit_text(f"🕐 Na fila — posição #{pos}. Aguarde...")
    else:
        await status_msg.edit_text("⏳ Gerando vídeo... pode demorar alguns minutos.")


def _cleanup_temp(path: str | None) -> None:
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


async def _daily_find(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job: run /find automatically every day."""
    chat_id = bot_config.allowed_user_ids[0]
    await context.bot.send_message(chat_id, "🔄 Busca diária iniciada...")
    await _run_find(context.bot, chat_id)
    await context.bot.send_message(chat_id, "🏁 Busca diária concluída.")


async def _post_init(application: Application) -> None:
    generation_queue.start()
    logger.info("Generation queue worker started")


def main() -> None:
    token = secrets.telegram_satisfying_bot_token
    if not token:
        raise RuntimeError("TELEGRAM_SATISFYING_BOT_TOKEN env var is not set")

    app = Application.builder().token(token).post_init(_post_init).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url),
        ],
        states={
            WAITING_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
    )

    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("find", cmd_find))
    app.add_handler(CallbackQueryHandler(handle_find_generate, pattern=f"^{FIND_CALLBACK_PREFIX}"))

    schedule_time = datetime.time(hour=bot_config.daily_hour_utc, tzinfo=datetime.timezone.utc)
    app.job_queue.run_daily(_daily_find, time=schedule_time)
    logger.info("Daily /find scheduled at %02d:00 UTC", bot_config.daily_hour_utc)

    logger.info("Satisfying video bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
