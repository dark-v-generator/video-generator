import json
import os
import tempfile
from dataclasses import dataclass
from typing import Literal, Optional
from ..proxies.interfaces import IImageGeneratorProxy, ILLMProxy, IRedditProxy
from ..entities.cover import RedditCover
from ..entities.editor import image_clip
from ..entities.editor.audio_clip import AudioClip
from ..entities.editor.captions_clip import CaptionsClip
from ..entities.language import Language
from .captions_service import CaptionsService
from .cover_service import CoverService
from .speech_service import SpeechService
from .video_service import VideoService


# ---------------------------------------------------------------------------
# Output data-classes
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


@dataclass
class ImageStoryVideoResult:
    """All generated artifacts for an image-story video."""

    part1_video: bytes
    part2_video: bytes
    story_md: str
    original_post_md: str
    audio_part1: bytes
    audio_part2: bytes
    captions_part1_json: str
    captions_part2_json: str
    image_story_part1_json: str
    image_story_part2_json: str
    cover_png: Optional[bytes] = None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class RedditVideoService:
    """Generates Reddit-story videos with either YouTube backgrounds or AI-generated images."""

    def __init__(
        self,
        reddit_proxy: IRedditProxy,
        llm_proxy: ILLMProxy,
        image_generation_proxy: IImageGeneratorProxy,
        speech_service: SpeechService,
        captions_service: CaptionsService,
        cover_service: CoverService,
        video_service: VideoService,
    ) -> None:
        self._reddit_proxy = reddit_proxy
        self._llm_proxy = llm_proxy
        self._image_generation_proxy = image_generation_proxy
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
            captions_part1_json=json.dumps(
                captions_1_data, ensure_ascii=False, indent=2
            ),
            captions_part2_json=json.dumps(
                captions_2_data, ensure_ascii=False, indent=2
            ),
            cover_png=cover_result.bytes,
        )

    async def generate_image_story_video(
        self,
        *,
        post_url: str,
        language: Language = Language.PORTUGUESE,
        speech_gender: Optional[Literal["male", "female"]] = None,
        speech_rate: float = 1.0,
        low_quality: bool = False,
    ) -> ImageStoryVideoResult:
        """Full pipeline: scrape → story → speech → captions → image story → images → video."""

        # 1. Scrape
        post = self._reddit_proxy.get_reddit_post(post_url)
        original_post_md = f"# {post.title}\n\n{post.content}\n"

        # 2. LLM: two-part story
        story = await self._llm_proxy.generate_two_part_story(
            title=post.title,
            content=post.content,
            target_language=language,
        )
        part1_text: str = story["part1"]
        part2_text: str = story["part2"]

        narrator_gender = story.get("narrator_gender", "unknown")
        resolved_gender: Literal["male", "female"] = speech_gender or (
            narrator_gender if narrator_gender in ("male", "female") else "male"
        )

        # 3. Speech
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

        # 4. Captions
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

        captions_1_data = [
            {"word": s.text, "start": s.start, "end": s.end}
            for s in captions_result_1.captions.segments
        ]
        captions_2_data = [
            {"word": s.text, "start": s.start, "end": s.end}
            for s in captions_result_2.captions.segments
        ]

        # 5. LLM: generate image stories from captions
        image_story_1 = await self._llm_proxy.generate_image_story(
            story_text=part1_text,
            transcription=captions_1_data,
        )
        image_story_2 = await self._llm_proxy.generate_image_story(
            story_text=part2_text,
            transcription=captions_2_data,
        )

        # 6. Generate images
        config = self._video_service._video_config
        img_w, img_h = config.width, config.height

        generated_images_1 = self._generate_images_for_story(
            image_story_1, img_w, img_h
        )
        generated_images_2 = self._generate_images_for_story(
            image_story_2, img_w, img_h
        )

        # 7. Cover
        cover_result = await self._cover_service.generate_cover(
            RedditCover(
                title=story.get("title", post.title),
                community=post.community,
                author=post.author,
                image_url=post.community_url_photo,
            )
        )

        # 8. Build story markdown
        story_md = f"# {story.get('title', 'Untitled')}\n\n"
        story_md += (
            f"**Narrator gender:** {narrator_gender} → resolved: {resolved_gender}\n\n"
        )
        story_md += f"## Part 1\n\n{part1_text}\n\n"
        story_md += f"## Part 2\n\n{part2_text}\n"

        # 9. Compose videos
        video_bytes_1 = self._render_image_story_to_bytes(
            audio=speech_result_1.clip,
            image_story=image_story_1,
            generated_images=generated_images_1,
            cover=cover_result.clip,
            captions=captions_result_1.clip,
            low_quality=low_quality,
        )
        video_bytes_2 = self._render_image_story_to_bytes(
            audio=speech_result_2.clip,
            image_story=image_story_2,
            generated_images=generated_images_2,
            cover=cover_result.clip,
            captions=captions_result_2.clip,
            low_quality=low_quality,
        )

        return ImageStoryVideoResult(
            part1_video=video_bytes_1,
            part2_video=video_bytes_2,
            story_md=story_md,
            original_post_md=original_post_md,
            audio_part1=speech_result_1.bytes,
            audio_part2=speech_result_2.bytes,
            captions_part1_json=json.dumps(
                captions_1_data, ensure_ascii=False, indent=2
            ),
            captions_part2_json=json.dumps(
                captions_2_data, ensure_ascii=False, indent=2
            ),
            image_story_part1_json=image_story_1.model_dump_json(indent=2),
            image_story_part2_json=image_story_2.model_dump_json(indent=2),
            cover_png=cover_result.bytes,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_images_for_story(self, image_story, width: int, height: int) -> list:
        generated = []
        for img_def in image_story.images:
            result = self._image_generation_proxy.generate_image(
                prompt=img_def.prompt,
                negative_prompt=None,
                width=width,
                height=height,
                num_images=1,
            )
            generated.append(result[0])
        return generated

    def _render_image_story_to_bytes(
        self,
        *,
        audio: AudioClip,
        image_story,
        generated_images: list,
        cover: Optional[image_clip.ImageClip],
        captions: Optional[CaptionsClip],
        low_quality: bool,
    ) -> bytes:
        final_video = self._video_service.generate_image_story_video(
            audio=audio,
            image_story=image_story,
            generated_images=generated_images,
            cover=cover,
            captions=captions,
            low_quality=low_quality,
        )
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            final_video.clip.write_videofile(
                tmp_path,
                fps=24,
                ffmpeg_params=self._video_service._video_config.ffmpeg_params,
            )
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

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
            )
            with open(tmp_path, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
