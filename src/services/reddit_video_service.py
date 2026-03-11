import json
import os
import tempfile
from dataclasses import dataclass
from typing import Literal, Optional
from ..proxies.interfaces import ILLMProxy, IRedditProxy
from ..entities.cover import RedditCover
from ..entities.editor import image_clip
from ..entities.editor.captions_clip import CaptionsClip
from ..entities.language import Language
from .captions_service import CaptionsService
from .cover_service import CoverService
from .speech_service import SpeechService
from .video_service import VideoService


# ---------------------------------------------------------------------------
# Output data-class
# ---------------------------------------------------------------------------


@dataclass
class TwoPartVideoResult:
    """All generated artifacts as in-memory bytes / strings."""

    part1_video: bytes
    part2_video: bytes
    story_md: str
    original_post_md: str
    audio_part1: bytes
    audio_part2: bytes
    captions_part1_json: str
    captions_part2_json: str
    cover_png: Optional[bytes] = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RedditVideoService:
    """Generates a two-part Reddit-story video backed by YouTube compilation."""

    def __init__(
        self,
        reddit_proxy: IRedditProxy,
        llm_proxy: ILLMProxy,
        speech_service: SpeechService,
        captions_service: CaptionsService,
        cover_service: CoverService,
        video_service: VideoService,
    ) -> None:
        self._reddit_proxy = reddit_proxy
        self._llm_proxy = llm_proxy
        self._speech_service = speech_service
        self._captions_service = captions_service
        self._cover_service = cover_service
        self._video_service = video_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_two_part_history_video(
        self,
        *,
        post_url: str,
        language: Language = Language.PORTUGUESE,
        speech_gender: Optional[Literal["male", "female"]] = None,
        speech_rate: float = 1.0,
        low_quality: bool = False,
    ) -> TwoPartVideoResult:
        """Full pipeline: scrape → two-part story → speech → captions → videos."""

        # ------------------------------------------------------------------ 1. Scrape
        post = self._reddit_proxy.get_reddit_post(post_url)

        # Build original post markdown
        original_post_md = f"# {post.title}\n\n{post.content}\n"

        # ------------------------------------------------------------------ 2. LLM: generate two-part story
        story = await self._llm_proxy.generate_two_part_story(
            title=post.title,
            content=post.content,
            target_language=language,
        )
        part1_text: str = story["part1"]
        part2_text: str = story["part2"]

        # Resolve TTS gender: manual override > LLM inference > default 'male'
        narrator_gender = story.get("narrator_gender", "unknown")
        resolved_gender: Literal["male", "female"] = speech_gender or (
            narrator_gender if narrator_gender in ("male", "female") else "male"
        )

        # ------------------------------------------------------------------ 3. Generate speech for both parts (returns SpeechResult)
        speech_result_1 = await self._speech_service.generate_speech(
            text=part1_text,
            gender=resolved_gender,
            rate=speech_rate,
            language=language,
        )

        speech_result_2 = await self._speech_service.generate_speech(
            text=part2_text,
            gender=resolved_gender,
            rate=speech_rate,
            language=language,
        )

        # ------------------------------------------------------------------ 4. Transcribe + enhance captions (returns CaptionsResult)
        captions_result_1 = await self._captions_service.generate_captions(
            audio_bytes=speech_result_1.bytes,
            enhance_captions=True,
            language=language,
            base_text=part1_text,
        )

        captions_result_2 = await self._captions_service.generate_captions(
            audio_bytes=speech_result_2.bytes,
            enhance_captions=True,
            language=language,
            base_text=part2_text,
        )

        # ------------------------------------------------------------------ 5. Generate cover from post data
        cover_result = await self._cover_service.generate_cover(
            RedditCover(
                title=story.get("title", post.title),
                community=post.community,
                author=post.author,
                image_url=post.community_url_photo,
            )
        )

        # ------------------------------------------------------------------ 6. Build artifact data
        story_md = f"# {story.get('title', 'Untitled')}\n\n"
        story_md += f"**Narrator gender:** {story.get('narrator_gender', 'unknown')} → resolved: {resolved_gender}\n\n"
        story_md += f"## Part 1\n\n{part1_text}\n\n"
        story_md += f"## Part 2\n\n{part2_text}\n"

        captions_1_data = [
            {"word": s.text, "start": s.start, "end": s.end}
            for s in captions_result_1.captions.segments
        ]
        captions_2_data = [
            {"word": s.text, "start": s.start, "end": s.end}
            for s in captions_result_2.captions.segments
        ]

        # ------------------------------------------------------------------ 7. Compose videos (write to temp files, read back as bytes)
        video_bytes_1 = await self._render_video_to_bytes(
            speech=speech_result_1.clip,
            captions_clip_obj=captions_result_1.clip,
            cover=cover_result.clip,
            low_quality=low_quality,
        )

        video_bytes_2 = await self._render_video_to_bytes(
            speech=speech_result_2.clip,
            captions_clip_obj=captions_result_2.clip,
            cover=cover_result.clip,
            low_quality=low_quality,
        )

        return TwoPartVideoResult(
            part1_video=video_bytes_1,
            part2_video=video_bytes_2,
            story_md=story_md,
            original_post_md=original_post_md,
            audio_part1=speech_result_1.bytes,
            audio_part2=speech_result_2.bytes,
            captions_part1_json=json.dumps(captions_1_data, ensure_ascii=False, indent=2),
            captions_part2_json=json.dumps(captions_2_data, ensure_ascii=False, indent=2),
            cover_png=cover_result.bytes,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _render_video_to_bytes(
        self,
        *,
        speech,
        captions_clip_obj: Optional[CaptionsClip],
        cover: Optional[image_clip.ImageClip],
        low_quality: bool,
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
        )

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            final_video.clip.write_videofile(
                tmp_path,
                ffmpeg_params=self._video_service._video_config.ffmpeg_params,
                logger=None,
            )
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
