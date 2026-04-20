"""Shared helpers for Telegram bots."""

import io
import logging
import subprocess
import tempfile

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


def is_user_allowed(user_id: int, allowed_ids: list[int]) -> bool:
    return user_id in allowed_ids


async def reject_unauthorized(update: Update) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(
        f"Você não tem permissão pra usar esse bot.\nSeu user ID: {user_id}"
    )


TELEGRAM_VIDEO_LIMIT = 49 * 1024 * 1024  # ~49 MB (Telegram caps at 50 MB)


def _compress_video(video_bytes: bytes, target_mb: int = 48) -> bytes:
    """Re-encode a video with ffmpeg to fit under *target_mb*."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as src:
        src.write(video_bytes)
        src_path = src.name
    dst_path = src_path.replace(".mp4", "_compressed.mp4")

    src_mb = len(video_bytes) / (1024 * 1024)
    # Pick CRF proportional to how far over the limit we are
    crf = min(40, max(28, int(23 + (src_mb / target_mb) * 5)))
    logger.info(
        "Compressing video: %.1f MB -> target %d MB (crf=%d)", src_mb, target_mb, crf
    )

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", src_path,
                "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                dst_path,
            ],
            capture_output=True,
            check=True,
        )
        with open(dst_path, "rb") as f:
            compressed = f.read()
        logger.info("Compressed: %.1f MB -> %.1f MB", src_mb, len(compressed) / (1024 * 1024))
        return compressed
    finally:
        import os
        os.unlink(src_path)
        if os.path.exists(dst_path):
            os.unlink(dst_path)


async def send_video_bytes(
    message,
    video_bytes: bytes,
    caption: str,
) -> None:
    """Send video as a reply. Compresses with ffmpeg if over Telegram's 50 MB limit."""
    if len(video_bytes) > TELEGRAM_VIDEO_LIMIT:
        video_bytes = _compress_video(video_bytes)

    await message.reply_video(
        video=io.BytesIO(video_bytes),
        caption=caption,
        filename="video.mp4",
        read_timeout=300,
        write_timeout=300,
    )


async def send_audio_bytes(
    message,
    audio_bytes: bytes,
    caption: str,
) -> None:
    """Send audio as a voice message. *message* can be any telegram Message object."""
    await message.reply_voice(
        voice=io.BytesIO(audio_bytes),
        caption=caption,
        read_timeout=120,
        write_timeout=120,
    )


async def send_image_bytes(
    message,
    image_bytes: bytes,
    caption: str,
) -> None:
    """Send a photo from in-memory bytes."""
    await message.reply_photo(
        photo=io.BytesIO(image_bytes),
        caption=caption,
        read_timeout=60,
        write_timeout=60,
    )
