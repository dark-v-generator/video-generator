import asyncio
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Literal, Optional

from ..entities.captions import Captions
from ..entities.cover import RedditCover
from ..entities.editor import image_clip
from ..entities.editor.captions_clip import CaptionsClip
from ..entities.language import Language
from ..entities.reddit_post import RedditPost
from ..proxies.interfaces import ILLMProxy, IRedditProxy
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
class PreparedStory:
    """Intermediate result from Stage 1: scrape + LLM story generation.

    Contains everything needed to produce the video without further LLM calls.
    """

    post: RedditPost
    script_text: str
    story_title: str
    narrator_gender: str
    resolved_gender: Literal["male", "female"]
    original_post_md: str


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
        reddit_proxy: IRedditProxy,
        llm_proxy: ILLMProxy,
        speech_service: SpeechService,
        captions_service: CaptionsService,
        cover_service: CoverService,
        video_service: VideoService,
        history_adaptation_llm_proxy: Optional[ILLMProxy] = None,
        text_censor: Optional[TextCensor] = None,
    ) -> None:
        self._reddit_proxy = reddit_proxy
        self._llm_proxy = llm_proxy
        self._history_adaptation_llm_proxy = history_adaptation_llm_proxy or llm_proxy
        self._speech_service = speech_service
        self._captions_service = captions_service
        self._cover_service = cover_service
        self._video_service = video_service
        self._text_censor = text_censor or TextCensor()

    def scrape_post(self, url: str) -> RedditPost:
        return self._reddit_proxy.get_reddit_post(url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def prepare_satisfying_story(
        self,
        *,
        post_url: str,
        language: Language = Language.PORTUGUESE,
        speech_gender: Optional[Literal["male", "female"]] = None,
    ) -> PreparedStory:
        """Stage 1: scrape + LLM story generation (the most failure-prone step)."""

        post = self.scrape_post(post_url)
        original_post_md = f"# {post.title}\n\n{post.content}\n"

        story = await self._history_adaptation_llm_proxy.generate_story(
            title=post.title,
            content=post.content,
            target_language=language,
        )
        script_text: str = story["script"]

        narrator_gender = story.get("narrator_gender", "unknown")
        resolved_gender: Literal["male", "female"] = speech_gender or (
            narrator_gender if narrator_gender in ("male", "female") else "male"
        )

        return PreparedStory(
            post=post,
            script_text=script_text,
            story_title=story.get("title", post.title),
            narrator_gender=narrator_gender,
            resolved_gender=resolved_gender,
            original_post_md=original_post_md,
        )

    async def generate_satisfying_video_from_story(
        self,
        prepared: PreparedStory,
        *,
        speech_rate: float = 1.0,
        low_quality: bool = False,
        language: Language = Language.PORTUGUESE,
    ) -> SingleVideoResult:
        """Stage 2: speech, captions, cover, video composition from an already-prepared story."""

        speech_result = await self._speech_service.generate_speech(
            text=prepared.script_text,
            gender=prepared.resolved_gender,
            rate=speech_rate,
            language=language,
        )

        captions_result = await self._captions_service.generate_captions(
            audio_bytes=speech_result.bytes,
            enhance_captions=True,
            language=language,
            base_text=prepared.script_text,
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
                title=self._text_censor.censor(prepared.story_title),
                community=prepared.post.community,
                author=prepared.post.author,
                image_url=prepared.post.community_url_photo,
            )
        )

        video_bytes = await self._render_video_to_bytes(
            speech=speech_result.clip,
            captions_clip_obj=captions_result.clip,
            cover=cover_result.clip,
            low_quality=low_quality,
            cta_start=cta_start_time,
        )

        story_md = f"# {prepared.story_title}\n\n"
        story_md += f"**Narrator gender:** {prepared.narrator_gender} → resolved: {prepared.resolved_gender}\n\n"
        story_md += f"{prepared.script_text}\n"

        return SingleVideoResult(
            video=video_bytes,
            story_md=story_md,
            original_post_md=prepared.original_post_md,
            audio=speech_result.bytes,
            captions_json=json.dumps(captions_data, ensure_ascii=False, indent=2),
            localized_title=prepared.story_title,
            cover_png=cover_result.bytes,
        )

    async def generate_satisfying_video(
        self,
        *,
        post_url: str,
        language: Language = Language.PORTUGUESE,
        speech_gender: Optional[Literal["male", "female"]] = None,
        speech_rate: float = 1.0,
        low_quality: bool = False,
    ) -> SingleVideoResult:
        """Full pipeline: scrape -> single story -> speech -> captions -> satisfying background video."""

        prepared = await self.prepare_satisfying_story(
            post_url=post_url,
            language=language,
            speech_gender=speech_gender,
        )
        return await self.generate_satisfying_video_from_story(
            prepared,
            speech_rate=speech_rate,
            low_quality=low_quality,
            language=language,
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
