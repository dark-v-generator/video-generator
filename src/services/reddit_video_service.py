import shutil
import tempfile
import threading
from dataclasses import dataclass
from typing import Literal, Optional
from ..proxies.interfaces import ILLMProxy, IRedditProxy
from ..entities.configs.services.captions import CaptionsConfig
from ..entities.configs.services.video import VideoConfig
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
    """Paths to the two generated MP4 files."""

    part1_path: str
    part2_path: str


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
        output_path_part1: str,
        output_path_part2: str,
        language: Language = Language.PORTUGUESE,
        speech_gender: Literal["male", "female"] = "male",
        speech_rate: float = 1.0,
        low_quality: bool = False,
    ) -> TwoPartVideoResult:
        """Full pipeline: scrape → two-part story → speech → captions → videos."""

        # ------------------------------------------------------------------ 1. Scrape
        post = self._reddit_proxy.get_reddit_post(post_url)

        # ------------------------------------------------------------------ 2. LLM: generate two-part story
        story = await self._llm_proxy.generate_two_part_story(
            title=post.title,
            content=post.content,
            target_language=language,
        )
        part1_text: str = story["part1"]
        part2_text: str = story["part2"]

        # ------------------------------------------------------------------ 3. Generate speech for both parts (returns SpeechResult)
        speech_result_1 = await self._speech_service.generate_speech(
            text=part1_text,
            gender=speech_gender,
            rate=speech_rate,
            language=language,
        )

        speech_result_2 = await self._speech_service.generate_speech(
            text=part2_text,
            gender=speech_gender,
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

        await self._generate_single_video(
            speech=speech_result_1.clip,
            captions_clip_obj=captions_result_1.clip,
            cover=cover_result.clip,
            output_path=output_path_part1,
            low_quality=low_quality,
        )

        await self._generate_single_video(
            speech=speech_result_2.clip,
            captions_clip_obj=captions_result_2.clip,
            cover=cover_result.clip,
            output_path=output_path_part2,
            low_quality=low_quality,
        )

        return TwoPartVideoResult(
            part1_path=output_path_part1, part2_path=output_path_part2
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _generate_single_video(
        self,
        *,
        speech,
        captions_clip_obj: Optional[CaptionsClip],
        cover: Optional[image_clip.ImageClip],
        output_path: str,
        low_quality: bool,
    ) -> str:
        """Compile a single video from speech + captions + YouTube background."""

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

        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp_path = tmp.name
            final_video.clip.write_videofile(
                tmp_path,
                ffmpeg_params=self._video_service._video_config.ffmpeg_params,
                logger=None,
            )
            shutil.move(tmp_path, output_path)
            return output_path
        except Exception as exc:
            raise exc
