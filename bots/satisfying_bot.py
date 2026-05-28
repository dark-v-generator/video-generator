"""Telegram bot que gera vídeos com fundo satisfatório a partir de URLs do Reddit."""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
import tempfile
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

import litellm

from src.core.container import container
from src.core.secrets import secrets
from src.entities.config import MainConfig
from src.entities.story_candidate import EvaluatedStory
from src.proxies.tiktok_publisher_proxy import BrowserUseTikTokPublisherProxy
from src.services.reddit_video_service import PreparedStory

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

config = MainConfig.from_yaml(os.environ.get("CONFIG_PATH", "config.yaml"))
bot_config = config.bots.satisfying_bot

WAITING_URL = 0


# ---------------------------------------------------------------------------
# Generation queue – processes video jobs sequentially so the bot stays
# responsive while heavy work runs in the background.
# ---------------------------------------------------------------------------

RETRY_CALLBACK_PREFIX = "retry:"


@dataclass
class _GenerationJob:
    url: str
    url_key: str
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
                language=config.language,
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
            retry_keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "🔄 Tentar de novo",
                    callback_data=f"{RETRY_CALLBACK_PREFIX}{job.url_key}",
                )]
            ])
            error_text = str(e)
            if len(error_text) > 300:
                error_text = error_text[:300] + "…"
            await job.status_message.edit_text(
                f"❌ Erro ao gerar vídeo: {error_text}",
                reply_markup=retry_keyboard,
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

    url_key = _store_url(url)
    job = _GenerationJob(url=url, url_key=url_key, reply_message=update.message, status_message=status_msg)
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


def _parse_subreddits(args: list[str] | None) -> list[str] | None:
    if not args:
        return None

    subreddits = []
    for arg in args:
        for item in arg.split(","):
            name = item.strip().removeprefix("r/").strip("/")
            if name:
                subreddits.append(name)

    return subreddits or None


def _format_find_message(
    i: int, story: EvaluatedStory, *, include_scores: bool = True,
) -> str:
    """Build the text body for a single story message."""
    post = story.post
    sub = post.community.replace("r/", "")

    if include_scores:
        notas = story.evaluation.get("notas", {})
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
    else:
        lines = [
            f"#{i + 1} — {post.title}",
            f"r/{sub}",
            "",
            story.resumo[:400],
        ]

    return "\n".join(lines)


async def _discover_stories(
    subreddits: list[str] | None = None,
) -> list[EvaluatedStory]:
    """Run the story-finder pipeline and return ranked results."""
    container.wire(modules=[__name__])
    finder = container.story_finder_service()
    return await finder.find_best_stories(
        sort="top",
        time_filter="day",
        top_per_sub=5,
        language=config.language,
        subreddits=subreddits,
    )


async def _run_find(
    bot,
    chat_id: int,
    subreddits: list[str] | None = None,
) -> None:
    """Core /find logic: discover and rank stories, send results with generate buttons."""
    try:
        results = await _discover_stories(subreddits)
    except Exception as e:
        logger.exception("Failed to find stories")
        await bot.send_message(chat_id, f"Erro ao buscar histórias: {e}")
        return

    if not results:
        await bot.send_message(chat_id, "Nenhuma história boa encontrada hoje.")
        return

    for i, story in enumerate(results):
        text = _format_find_message(i, story, include_scores=True)
        url_key = _store_url(story.post.url)

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

    subreddits = _parse_subreddits(context.args)
    if subreddits:
        subs_text = ", ".join(f"r/{sub}" for sub in subreddits)
        await update.message.reply_text(
            f"Buscando as melhores histórias em {subs_text}... pode demorar um pouco."
        )
    else:
        await update.message.reply_text(
            "Buscando as melhores histórias do dia... pode demorar um pouco."
        )
    await _run_find(context.bot, update.effective_chat.id, subreddits=subreddits)


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

    job = _GenerationJob(url=url, url_key=url_key, reply_message=query.message, status_message=status_msg)
    pos = await generation_queue.enqueue(job)

    if pos > 1:
        await status_msg.edit_text(f"🕐 Na fila — posição #{pos}. Aguarde...")
    else:
        await status_msg.edit_text("⏳ Gerando vídeo... pode demorar alguns minutos.")


async def handle_retry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_user_allowed(user_id, bot_config.allowed_user_ids):
        await query.message.reply_text("Sem permissão.")
        return

    url_key = query.data.removeprefix(RETRY_CALLBACK_PREFIX)
    url = _find_url_store.get(url_key)
    if not url:
        await query.message.reply_text("Link expirado. Rode /find de novo.")
        return

    await query.edit_message_reply_markup(reply_markup=None)
    status_msg = await query.message.reply_text("⏳ Adicionando à fila...")

    job = _GenerationJob(url=url, url_key=url_key, reply_message=query.message, status_message=status_msg)
    pos = await generation_queue.enqueue(job)

    if pos > 1:
        await status_msg.edit_text(f"🕐 Na fila — posição #{pos}. Aguarde...")
    else:
        await status_msg.edit_text("⏳ Tentando de novo... pode demorar alguns minutos.")


def _cleanup_temp(path: str | None) -> None:
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass


def _parse_slot_times(slot_times: list[str]) -> list[datetime.time]:
    """Parse and sort HH:MM strings into time objects."""
    parsed = sorted(
        datetime.time(int(h), int(m))
        for h, m in (s.split(":") for s in slot_times)
    )
    if not parsed:
        raise ValueError("publish_slots_local must contain at least one HH:MM entry")
    return parsed


def next_publish_slot(
    after: datetime.datetime,
    slot_times: list[str],
    min_lead_minutes: int,
    *,
    _now: datetime.datetime | None = None,
) -> datetime.datetime:
    """Return the first eligible slot strictly after *after*.

    Respects *min_lead_minutes* relative to the real clock (now), and
    also ensures the slot comes after the previous scheduled time so
    slots never go backwards.
    """
    parsed = _parse_slot_times(slot_times)
    now = _now or datetime.datetime.now()
    earliest = max(
        after + datetime.timedelta(minutes=1),
        now + datetime.timedelta(minutes=min_lead_minutes),
    )
    day = earliest.date()

    for _ in range(400):
        for t in parsed:
            candidate = datetime.datetime.combine(day, t)
            if candidate >= earliest:
                return candidate
        day += datetime.timedelta(days=1)

    raise RuntimeError("Could not find a valid publish slot within 400 days")


def compute_publish_slots(
    now: datetime.datetime,
    slot_times: list[str],
    count: int,
    min_lead_minutes: int,
) -> list[datetime.datetime]:
    """Return the next *count* eligible local-time publish slots starting from *now*.

    Walks configured HH:MM slots forward day-by-day, skipping any slot
    that falls within *min_lead_minutes* of *now*.
    """
    parsed = _parse_slot_times(slot_times)
    earliest = now + datetime.timedelta(minutes=min_lead_minutes)
    day = now.date()
    slots: list[datetime.datetime] = []

    while len(slots) < count:
        for t in parsed:
            candidate = datetime.datetime.combine(day, t)
            if candidate >= earliest and len(slots) < count:
                slots.append(candidate)
        day += datetime.timedelta(days=1)

    return slots


def _build_tiktok_publisher() -> BrowserUseTikTokPublisherProxy:
    """Instantiate the TikTok publisher using project config + secrets."""
    pub_cfg = config.proxies.tiktok_publisher_config
    return BrowserUseTikTokPublisherProxy(
        openrouter_api_key=secrets.openrouter_api_key,
        model=pub_cfg.agent_model,
        cookies_path=pub_cfg.cookies_path,
        headless=pub_cfg.headless,
        max_steps=pub_cfg.max_steps,
        use_vision=pub_cfg.use_vision,
    )


import json as _json


_DEFAULT_OUTPUT_DIR = "output/daily"


@dataclass
class GeneratedVideo:
    """Metadata for a generated video ready to publish."""
    video_path: str
    title: str
    summary: str
    post_url: str


def _save_manifest(video: GeneratedVideo, output_dir: str) -> None:
    manifest = {
        "video_path": video.video_path,
        "title": video.title,
        "summary": video.summary,
        "post_url": video.post_url,
    }
    base = os.path.splitext(os.path.basename(video.video_path))[0]
    path = os.path.join(output_dir, f"{base}.json")
    with open(path, "w") as f:
        _json.dump(manifest, f, ensure_ascii=False, indent=2)


def load_generated_videos(directory: str) -> list[GeneratedVideo]:
    """Load previously generated videos from a directory of .json manifests."""
    videos = []
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        with open(path) as f:
            data = _json.load(f)
        mp4 = data["video_path"]
        if not os.path.isabs(mp4):
            mp4 = os.path.join(directory, os.path.basename(mp4))
        if not os.path.exists(mp4):
            logger.warning("Video file missing, skipping: %s", mp4)
            continue
        videos.append(GeneratedVideo(
            video_path=mp4,
            title=data["title"],
            summary=data.get("summary", ""),
            post_url=data.get("post_url", ""),
        ))
    return videos


_STORY_RETRY_MAX = 3
_STORY_RETRY_BASE_DELAY = 5
_daily_auto_publish_lock: asyncio.Lock | None = None


def _is_transient_error(exc: Exception) -> bool:
    """Return True for errors that are worth retrying (rate-limits, timeouts, server errors)."""
    if isinstance(exc, litellm.RateLimitError):
        return True

    exc_str = str(exc).lower()
    transient_signals = ["429", "rate limit", "too many requests", "timeout", "503", "502"]
    return any(s in exc_str for s in transient_signals)


def _is_content_filter_error(exc: Exception) -> bool:
    """Return True for errors caused by content/safety filters (not worth retrying)."""
    exc_str = str(exc).lower()
    filter_signals = ["safety filter", "content filter", "nsfw", "blocked", "content policy"]
    return any(s in exc_str for s in filter_signals)


def _truncate_error(exc: Exception, limit: int = 300) -> str:
    error_text = str(exc)
    if len(error_text) > limit:
        error_text = error_text[:limit] + "…"
    return error_text


def _target_count(results: list[EvaluatedStory], publish_count: int | None) -> int:
    return min(
        publish_count
        if publish_count is not None
        else bot_config.daily_auto_publish_count,
        len(results),
    )


async def _prepare_story_with_retries(
    send_message,
    service,
    story: EvaluatedStory,
    *,
    candidate_number: int,
    target_count: int,
) -> PreparedStory | None:
    post = story.post
    label = f"#{candidate_number} — {post.title[:60]}"

    for attempt in range(1, _STORY_RETRY_MAX + 1):
        try:
            await send_message(f"📝 [{label}] Gerando roteiro...")
            prepared = await service.prepare_satisfying_story(
                post_url=post.url,
                language=config.language,
            )
            await send_message(f"✅ [{label}] Roteiro pronto")
            return prepared

        except Exception as e:
            if _is_content_filter_error(e):
                logger.warning("Content filter on %s, skipping: %s", post.url, e)
                await send_message(
                    f"⚠️ [{label}] Bloqueado por filtro de conteúdo, pulando."
                )
                return None

            if _is_transient_error(e) and attempt < _STORY_RETRY_MAX:
                delay = _STORY_RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "Transient error on %s (attempt %d/%d), retrying in %ds: %s",
                    post.url, attempt, _STORY_RETRY_MAX, delay, e,
                )
                await send_message(
                    f"⏳ [{label}] Erro temporário, tentando de novo em {delay}s "
                    f"(tentativa {attempt}/{_STORY_RETRY_MAX})..."
                )
                await asyncio.sleep(delay)
                continue

            logger.exception(
                "Failed to prepare story for %s (attempt %d/%d)",
                post.url, attempt, _STORY_RETRY_MAX,
            )
            await send_message(
                f"❌ [{label}] Erro no roteiro: {_truncate_error(e)}. "
                f"Tentando outra história para completar {target_count}."
            )
            return None

    return None


async def _generate_video_for_story(
    send_message,
    service,
    prepared: PreparedStory,
    story: EvaluatedStory,
    *,
    output_dir: str,
    candidate_number: int,
    success_number: int,
    target_count: int,
) -> GeneratedVideo | None:
    label = f"#{candidate_number} — {prepared.story_title[:60]}"
    await send_message(
        f"⏳ [{label}] Gerando vídeo ({success_number}/{target_count})..."
    )

    try:
        result = await service.generate_satisfying_video_from_story(
            prepared,
            language=config.language,
            low_quality=bot_config.low_quality,
        )

        video_path = os.path.join(output_dir, f"story_{candidate_number:02d}.mp4")
        with open(video_path, "wb") as f:
            f.write(result.video)

        video = GeneratedVideo(
            video_path=video_path,
            title=result.localized_title,
            summary=story.resumo[:400],
            post_url=prepared.post.url,
        )
        _save_manifest(video, output_dir)

        await send_message(f"💾 [{label}] Vídeo salvo em {video_path}")
        return video

    except Exception as e:
        logger.exception("Failed to generate video for %s", prepared.post.url)
        await send_message(
            f"❌ [{label}] Erro na geração de vídeo: {_truncate_error(e)}. "
            "Pulando para a próxima história."
        )
        return None


async def _publish_one_video(
    send_message,
    llm_proxy,
    publisher,
    video: GeneratedVideo,
    *,
    last_slot: datetime.datetime,
    success_number: int,
    target_count: int,
) -> datetime.datetime | None:
    label = f"#{success_number} — {video.title[:60]}"

    try:
        slot = next_publish_slot(
            after=last_slot,
            slot_times=bot_config.publish_slots_local,
            min_lead_minutes=bot_config.publish_min_lead_minutes,
        )

        hashtags = await llm_proxy.generate_hashtags(
            title=video.title,
            summary=video.summary,
            target_language=config.language,
        )

        await send_message(
            f"📤 [{label}] Agendando para {slot.strftime('%d/%m %H:%M')} "
            f"({success_number}/{target_count})...",
        )

        publish_result = await publisher.publish_video(
            video_path=video.video_path,
            description=video.title,
            hashtags=hashtags,
            schedule_at=slot,
        )

        msg = f"✅ [{label}] Agendado — {slot.strftime('%d/%m %H:%M')}"
        if publish_result:
            msg += f"\n{publish_result}"
        await send_message(msg)
        return slot

    except Exception as e:
        logger.exception("Failed to publish %s", video.video_path)
        await send_message(
            f"❌ [{label}] Erro ao publicar: {_truncate_error(e)}. "
            "Pulando para uma nova história."
        )
        return None


async def run_daily_generate(
    send_message,
    *,
    publish_count: int | None = None,
    output_dir: str = _DEFAULT_OUTPUT_DIR,
) -> list[GeneratedVideo]:
    """Discover stories and generate videos one candidate at a time."""
    await send_message("🔄 Busca diária iniciada...")

    try:
        results = await _discover_stories()
    except Exception as e:
        logger.exception("Failed to find stories")
        await send_message(f"Erro ao buscar histórias: {e}")
        return []

    if not results:
        await send_message("Nenhuma história boa encontrada hoje.")
        return []

    for i, story in enumerate(results):
        text = _format_find_message(i, story, include_scores=False)
        await send_message(text)

    await send_message(f"{len(results)} histórias encontradas.")

    count = _target_count(results, publish_count)
    if count == 0:
        return []

    os.makedirs(output_dir, exist_ok=True)

    container.wire(modules=[__name__])
    service = container.reddit_video_service()

    await send_message(f"🎬 Gerando até {count} vídeos em fluxo sequencial...")
    generated: list[GeneratedVideo] = []

    for candidate_idx, story in enumerate(results, start=1):
        if len(generated) >= count:
            break

        prepared = await _prepare_story_with_retries(
            send_message,
            service,
            story,
            candidate_number=candidate_idx,
            target_count=count,
        )
        if prepared is None:
            continue

        video = await _generate_video_for_story(
            send_message,
            service,
            prepared,
            story,
            output_dir=output_dir,
            candidate_number=candidate_idx,
            success_number=len(generated) + 1,
            target_count=count,
        )
        if video is not None:
            generated.append(video)

    await send_message(
        f"🏁 Geração concluída: {len(generated)}/{count} vídeos salvos "
        f"em {output_dir}",
    )
    return generated


async def run_daily_publish(
    send_message,
    videos: list[GeneratedVideo],
) -> None:
    """Stage 3: Schedule pre-generated videos on TikTok."""
    if not videos:
        await send_message("Nenhum vídeo para publicar.")
        return

    await send_message(f"📤 Agendando {len(videos)} vídeos...")

    container.wire(modules=[__name__])
    llm_proxy = container.llm_proxy()
    publisher = _build_tiktok_publisher()

    last_slot = datetime.datetime.now()

    for idx, video in enumerate(videos):
        label = f"#{idx + 1} — {video.title[:60]}"

        try:
            slot = next_publish_slot(
                after=last_slot,
                slot_times=bot_config.publish_slots_local,
                min_lead_minutes=bot_config.publish_min_lead_minutes,
            )

            hashtags = await llm_proxy.generate_hashtags(
                title=video.title,
                summary=video.summary,
                target_language=config.language,
            )

            await send_message(
                f"📤 [{label}] Agendando para {slot.strftime('%d/%m %H:%M')}...",
            )

            publish_result = await publisher.publish_video(
                video_path=video.video_path,
                description=video.title,
                hashtags=hashtags,
                schedule_at=slot,
            )

            last_slot = slot

            msg = f"✅ [{label}] Agendado — {slot.strftime('%d/%m %H:%M')}"
            if publish_result:
                msg += f"\n{publish_result}"
            await send_message(msg)

        except Exception as e:
            logger.exception("Failed to publish %s", video.video_path)
            error_text = str(e)
            if len(error_text) > 300:
                error_text = error_text[:300] + "…"
            await send_message(f"❌ [{label}] Erro: {error_text}")

    await send_message("🏁 Agendamento concluído.")


async def run_daily_auto_publish(
    send_message,
    *,
    publish_count: int | None = None,
    output_dir: str = _DEFAULT_OUTPUT_DIR,
) -> None:
    """Full pipeline: for each candidate, run story -> video -> publish."""
    await send_message("🔄 Busca diária iniciada...")

    try:
        results = await _discover_stories()
    except Exception as e:
        logger.exception("Failed to find stories")
        await send_message(f"Erro ao buscar histórias: {e}")
        return

    if not results:
        await send_message("Nenhuma história boa encontrada hoje.")
        return

    for i, story in enumerate(results):
        text = _format_find_message(i, story, include_scores=False)
        await send_message(text)

    await send_message(f"{len(results)} histórias encontradas.")

    count = _target_count(results, publish_count)
    if count == 0:
        return

    os.makedirs(output_dir, exist_ok=True)

    container.wire(modules=[__name__])
    service = container.reddit_video_service()
    llm_proxy = container.llm_proxy()
    publisher = _build_tiktok_publisher()

    last_slot = datetime.datetime.now()
    published = 0

    await send_message(
        "🎬 Fluxo e2e iniciado: roteiro → vídeo → agendamento para cada "
        f"história até completar {count} publicações."
    )

    for candidate_idx, story in enumerate(results, start=1):
        if published >= count:
            break

        prepared = await _prepare_story_with_retries(
            send_message,
            service,
            story,
            candidate_number=candidate_idx,
            target_count=count,
        )
        if prepared is None:
            continue

        video = await _generate_video_for_story(
            send_message,
            service,
            prepared,
            story,
            output_dir=output_dir,
            candidate_number=candidate_idx,
            success_number=published + 1,
            target_count=count,
        )
        if video is None:
            continue

        slot = await _publish_one_video(
            send_message,
            llm_proxy,
            publisher,
            video,
            last_slot=last_slot,
            success_number=published + 1,
            target_count=count,
        )
        if slot is None:
            continue

        last_slot = slot
        published += 1

    await send_message(
        f"🏁 Pipeline e2e concluído: {published}/{count} vídeos agendados."
    )


def _get_daily_auto_publish_lock() -> asyncio.Lock:
    global _daily_auto_publish_lock
    if _daily_auto_publish_lock is None:
        _daily_auto_publish_lock = asyncio.Lock()
    return _daily_auto_publish_lock


async def _run_daily_auto_publish_locked(
    send_message,
    *,
    publish_count: int | None = None,
) -> None:
    lock = _get_daily_auto_publish_lock()
    if lock.locked():
        await send_message("Já existe um fluxo de auto-post em andamento.")
        return

    async with lock:
        await run_daily_auto_publish(send_message, publish_count=publish_count)


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

    if command == "/find":
        await cmd_find(update, context)
        return True

    return False


async def cmd_autopost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    if not is_user_allowed(user_id, bot_config.allowed_user_ids):
        await reject_unauthorized(update)
        return

    try:
        publish_count = _parse_optional_count(context.args)
    except ValueError as e:
        await update.message.reply_text(str(e))
        return

    chat_id = update.effective_chat.id

    async def send_message(text: str) -> None:
        await context.bot.send_message(chat_id, text)

    await send_message("🚀 Auto-post manual iniciado.")
    await _run_daily_auto_publish_locked(
        send_message,
        publish_count=publish_count,
    )


async def _daily_find(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Scheduled job: discover stories, send summaries, auto-generate and schedule videos."""
    chat_id = bot_config.allowed_user_ids[0]
    bot = context.bot

    async def send_message(text: str) -> None:
        await bot.send_message(chat_id, text)

    await _run_daily_auto_publish_locked(send_message)


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
    app.add_handler(CommandHandler(["autopost", "auto_publish"], cmd_autopost))
    app.add_handler(CallbackQueryHandler(handle_find_generate, pattern=f"^{FIND_CALLBACK_PREFIX}"))
    app.add_handler(CallbackQueryHandler(handle_retry, pattern=f"^{RETRY_CALLBACK_PREFIX}"))

    schedule_time = datetime.time(
        hour=bot_config.daily_hour_utc,
        minute=bot_config.daily_minute_utc,
        tzinfo=datetime.timezone.utc,
    )
    app.job_queue.run_daily(_daily_find, time=schedule_time)
    logger.info(
        "Daily /find scheduled at %02d:%02d UTC",
        bot_config.daily_hour_utc,
        bot_config.daily_minute_utc,
    )

    logger.info("Satisfying video bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
