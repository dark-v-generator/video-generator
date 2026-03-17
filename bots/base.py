"""Shared helpers for Telegram bots."""

import io
import logging
from typing import List

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def is_user_allowed(user_id: int, allowed_ids: List[int]) -> bool:
    return user_id in allowed_ids


async def reject_unauthorized(update: Update) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"You are not authorized to use this bot.\nYour user ID: {user_id}"
    )


async def send_video_bytes(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    video_bytes: bytes,
    caption: str,
) -> None:
    await update.message.reply_video(
        video=io.BytesIO(video_bytes),
        caption=caption,
        filename="video.mp4",
        read_timeout=300,
        write_timeout=300,
    )
