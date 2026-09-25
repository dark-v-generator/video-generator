import asyncio
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Optional

from ..entities.captions import Captions
from ..entities.cover import RedditCover
from ..entities.editor import image_clip
from ..entities.editor.captions_clip import CaptionsClip
from ..entities.story import Story
from .captions_service import CaptionsService
from .cover_service import CoverService
from .speech_service import SpeechService
from .text_censor import TextCensor
from .video_service import VideoService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data-classes
# ---------------------------------------------------------------------------


@dataclass
class SingleVideoResult:
    """All generated artifacts for a single satisfying-background video."""

    video: bytes
    story_md: str
    original_post_md: str
    audio: bytes
    captions_json: str
    localized_title: str
    cover_png: Optional[bytes] = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RedditVideoService:
    """Generates single Reddit-story videos over a YouTube background compilation."""

    def __init__(
        self,
        speech_service: SpeechService,
        captions_service: CaptionsService,
        cover_service: CoverService,
        video_service: VideoService,
        text_censor: Optional[TextCensor] = None,
    ) -> None:
        self._speech_service = speech_service
        self._captions_service = captions_service
        self._cover_service = cover_service
        self._video_service = video_service
        self._text_censor = text_censor or TextCensor()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_satisfying_video_from_story(
        self,
        story: Story,
        *,
        speech_rate: float = 1.0,
        low_quality: bool = False,
    ) -> SingleVideoResult:
        """Speech, captions, cover and video composition for a one-part story."""

        if story.is_multipart:
            raise ValueError(
                f"Cannot render a {len(story.parts)}-part story as a single video"
            )
        (part,) = story.parts
        cover_title = story.cover_title_for(part)

        speech_result = await self._speech_service.generate_speech(
            text=part.text,
            gender=story.resolved_gender,
            rate=speech_rate,
            language=story.language,
        )

        captions_result = await self._captions_service.generate_captions(
            audio_bytes=speech_result.bytes,
            enhance_captions=True,
            language=story.language,
            base_text=part.text,
        )

        segments_data = [
            {"word": s.text, "start": s.start, "end": s.end}
            for s in captions_result.captions.segments
        ]

        cta_start_time = self._compute_satisfying_cta_start(segments_data)

        # The title is not narrated (it lives on the cover), so the whole
        # transcription is story content — nothing is trimmed. The cover gets
        # its own slot at the front of the video instead.
        captions_data = self._text_censor.censor_word_dicts(segments_data)

        captions_result.clip.captions = Captions(
            segments=self._text_censor.censor_segments(
                captions_result.clip.captions.segments
            )
        )

        cover_result = await self._cover_service.generate_cover(
            RedditCover(
                title=self._text_censor.censor(cover_title),
                community=story.origin.community,
                author=story.origin.author,
                image_url=story.origin.community_image_url,
            )
        )

        video_bytes = await self._render_video_to_bytes(
            speech=speech_result.clip,
            captions_clip_obj=captions_result.clip,
            cover=cover_result.clip,
            low_quality=low_quality,
            cta_start=cta_start_time,
        )

        return SingleVideoResult(
            video=video_bytes,
            story_md=story.story_markdown,
            original_post_md=story.origin.original_markdown,
            audio=speech_result.bytes,
            captions_json=json.dumps(captions_data, ensure_ascii=False, indent=2),
            localized_title=cover_title,
            cover_png=cover_result.bytes,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    CTA_START_WORDS = {
        "curta",
        "like",
        "dale",
        "deja",
        "laisse",
        "lascia",
        "gib",
    }

    @classmethod
    def _normalize_marker_word(cls, word: str) -> str:
        return word.strip().lower().strip(".,!?;:¿¡")

    @staticmethod
    def _compute_satisfying_cta_start(segments: list[dict]) -> float:
        """Find when the call-to-action starts in a single-story video.

        The title is not narrated, so there is no spoken intro to detect —
        only the CTA, found by looking for "curta" in the last ~20 words.
        Times are relative to the narration; the renderer shifts them when it
        puts the cover in front.
        """
        n = len(segments)
        if n == 0:
            return 0.0

        cta_start_time = segments[-3]["start"] if n > 3 else segments[0]["start"]
        for i in range(max(0, n - 20), n):
            word = RedditVideoService._normalize_marker_word(
                segments[i].get("word", "")
            )
            if word in RedditVideoService.CTA_START_WORDS:
                return segments[i]["start"]

        return cta_start_time

    async def _render_video_to_bytes(
        self,
        *,
        speech,
        captions_clip_obj: Optional[CaptionsClip],
        cover: Optional[image_clip.ImageClip],
        low_quality: bool,
        cta_start: float = 0,
    ) -> bytes:
        """Compile a single video and return it as bytes."""

        # Download YouTube compilation background
        compilation_result = await self._video_service.create_youtube_video_compilation(
            min_duration=speech.clip.duration,
            low_quality=low_quality,
        )
        background_video = compilation_result.clip

        if background_video is None:
            raise RuntimeError("Failed to create background video compilation.")

        # Compose
        final_video = self._video_service.generate_video(
            audio=speech,
            background_video=background_video,
            low_quality=low_quality,
            cover=cover,
            captions=captions_clip_obj,
            cta_start=cta_start,
        )

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name

        def _write_and_read() -> bytes:
            try:
                final_video.clip.write_videofile(
                    tmp_path,
                    fps=self._video_service._video_config.fps,
                    ffmpeg_params=self._video_service._video_config.ffmpeg_params,
                )
                with open(tmp_path, "rb") as f:
                    return f.read()
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        return await asyncio.to_thread(_write_and_read)
