"""Telegram bot that runs the daily flow and turns a Reddit URL into a video.

An adapter: the daily run (``/autopost`` and the daily job) is ``DailyRun`` with
progress sent to the chat; a Reddit URL goes through discovery, writing and
rendering on a sequential job queue so the bot stays responsive.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from dataclasses import dataclass
from typing import Optional

from telegram import Message, Update
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
from src.flows.progress import Progress, RunLock, short_error

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

config = container.main_config()
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
    def position(self) -> int:
        """Position a newly enqueued job would have (1-based, counting the running job)."""
        return self._queue.qsize() + (1 if self._running else 0) + 1

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

            origin = container.story_discovery().fetch(job.url)
            story = await container.story_writer().write(
                origin, language=config.language
            )
            rendered = await container.renderer().render(
                story, low_quality=bot_config.low_quality
            )

            for part in rendered:
                suffix = f" — parte {part.part.index}" if story.is_multipart else ""
                await job.status_message.edit_text(f"📤 Enviando áudio{suffix}...")
                await send_audio_bytes(
                    job.reply_message, part.audio, f"Narração{suffix}"
                )

                video_mb = len(part.video) / (1024 * 1024)
                if video_mb > 49:
                    await job.status_message.edit_text(
                        f"📤 Comprimindo vídeo{suffix} ({video_mb:.0f} MB)... "
                        "pode demorar."
                    )
                else:
                    await job.status_message.edit_text(f"📤 Enviando vídeo{suffix}...")
                await send_video_bytes(
                    job.reply_message, part.video, f"Vídeo pronto{suffix}"
                )

            await job.status_message.edit_text("✅ Vídeo pronto!")

        except Exception as e:
            logger.exception("Failed to generate video for %s", job.url)
            await job.status_message.edit_text(
                f"❌ Erro ao gerar vídeo: {short_error(e)}"
            )


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
    if url.startswith("/"):
        handled = await _handle_text_command(update, context, url)
        return ConversationHandler.END if handled else WAITING_URL

    if "reddit.com" not in url:
        await update.message.reply_text("Manda um link válido do Reddit.")
        return WAITING_URL

    logger.info("User %s requested satisfying video for: %s", user_id, url)
    status_msg = await update.message.reply_text("⏳ Adicionando à fila...")

    job = _GenerationJob(
        url=url, reply_message=update.message, status_message=status_msg
    )
    pos = await generation_queue.enqueue(job)

    if pos > 1:
        await status_msg.edit_text(f"🕐 Na fila — posição #{pos}. Aguarde...")
    else:
        await status_msg.edit_text("⏳ Gerando vídeo... pode demorar alguns minutos.")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Daily run: /autopost and the daily job share one run at a time.
# ---------------------------------------------------------------------------

run_lock = RunLock()


async def _run_daily(progress: Progress, count: int | None = None) -> None:
    if run_lock.locked:
        await progress("Já existe um fluxo de auto-post em andamento.")
        return

    async with run_lock:
        await container.daily_run(progress=progress).run(count=count)


def _parse_optional_count(args: list[str] | None) -> int | None:
    if not args:
        return None

    try:
        count = int(args[0])
    except ValueError as exc:
        raise ValueError("Use /autopost ou /autopost 2") from exc

    if count < 1:
        raise ValueError("A quantidade precisa ser maior que zero.")
    return count


def _split_text_command(text: str) -> tuple[str, list[str]]:
    parts = text.strip().split()
    command = parts[0].split("@", 1)[0].lower()
    return command, parts[1:]


async def _handle_text_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> bool:
    command, args = _split_text_command(text)
    context.args = args

    if command in ("/autopost", "/auto_publish"):
        await cmd_autopost(update, context)
        return True

    return False


async def cmd_autopost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_allowed(user_id, bot_config.allowed_user_ids):
        await reject_unauthorized(update)
        return

    try:
        count = _parse_optional_count(context.args)
    except ValueError as e:
        await update.message.reply_text(str(e))
        return

    chat_id = update.effective_chat.id

    async def send_message(text: str) -> None:
        await context.bot.send_message(chat_id, text)

    await send_message("🚀 Auto-post manual iniciado.")
    await _run_daily(send_message, count=count)


async def _daily_find(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job: the full daily run, reported to the first allowed user."""
    chat_id = bot_config.allowed_user_ids[0]
    bot = context.bot

    async def send_message(text: str) -> None:
        await bot.send_message(chat_id, text)

    await _run_daily(send_message)


async def _post_init(application: Application) -> None:
    generation_queue.start()


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
    app.add_handler(CommandHandler(["autopost", "auto_publish"], cmd_autopost))

    schedule_time = datetime.time(
        hour=bot_config.daily_hour_utc,
        minute=bot_config.daily_minute_utc,
        tzinfo=datetime.timezone.utc,
    )
    app.job_queue.run_daily(_daily_find, time=schedule_time)
    logger.info(
        "Daily run scheduled at %02d:%02d UTC",
        bot_config.daily_hour_utc,
        bot_config.daily_minute_utc,
    )

    logger.info("Satisfying video bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
