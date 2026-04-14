import json
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Literal, Optional

from ..entities.cover import RedditCover
from ..entities.editor import image_clip
from ..entities.image_story import ImageStory
from ..entities.editor.audio_clip import AudioClip
from ..entities.editor.captions_clip import CaptionsClip
from ..entities.language import Language
from ..entities.reddit_post import RedditPost
from ..proxies.interfaces import IImageGeneratorProxy, ILLMProxy, IRedditProxy
from .captions_service import CaptionsResult, CaptionsService
from .cover_service import CoverResult, CoverService
from .speech_service import SpeechResult, SpeechService
from .video_service import VideoService


# ---------------------------------------------------------------------------
# Intermediate data-classes (used by the checkpoint flow)
# ---------------------------------------------------------------------------


@dataclass
class StoryScript:
    title: str
    part1: str
    part2: str
    narrator_gender: str
    resolved_gender: Literal["male", "female"]


@dataclass
class AudioPair:
    part1: SpeechResult
    part2: SpeechResult


@dataclass
class CaptionsPair:
    part1: CaptionsResult
    part2: CaptionsResult
    part1_data: list[dict]
    part2_data: list[dict]


@dataclass
class ImageStoryPair:
    part1: ImageStory
    part2: ImageStory
    generated_images_1: list[bytes]
    generated_images_2: list[bytes]


@dataclass
class VideoPair:
    part1_video: bytes
    part2_video: bytes


# ---------------------------------------------------------------------------
# Final output data-classes
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
    # Step methods (used individually by the interactive bot)
    # ------------------------------------------------------------------

    def scrape_post(self, url: str) -> RedditPost:
        return self._reddit_proxy.get_reddit_post(url)

    async def generate_script(
        self,
        post: RedditPost,
        language: Language = Language.PORTUGUESE,
        speech_gender: Optional[Literal["male", "female"]] = None,
    ) -> StoryScript:
        story = await self._llm_proxy.generate_two_part_story(
            title=post.title,
            content=post.content,
            target_language=language,
        )
        narrator_gender = story.get("narrator_gender", "unknown")
        resolved_gender: Literal["male", "female"] = speech_gender or (
            narrator_gender if narrator_gender in ("male", "female") else "male"
        )
        return StoryScript(
            title=story.get("title", post.title),
            part1=story["part1"],
            part2=story["part2"],
            narrator_gender=narrator_gender,
            resolved_gender=resolved_gender,
        )

    async def revise_script(
        self,
        script: StoryScript,
        feedback: str,
        language: Language = Language.PORTUGUESE,
    ) -> StoryScript:
        revised = await self._llm_proxy.revise_story(
            current_script={
                "title": script.title,
                "part1": script.part1,
                "part2": script.part2,
                "narrator_gender": script.narrator_gender,
            },
            feedback=feedback,
            target_language=language,
        )
        return StoryScript(
            title=revised.get("title", script.title),
            part1=revised["part1"],
            part2=revised["part2"],
            narrator_gender=revised.get("narrator_gender", script.narrator_gender),
            resolved_gender=script.resolved_gender,
        )

    async def generate_audio(
        self,
        script: StoryScript,
        speech_rate: float = 1.0,
        language: Language = Language.PORTUGUESE,
    ) -> AudioPair:
        part1 = await self._speech_service.generate_speech(
            text=script.part1,
            gender=script.resolved_gender,
            rate=speech_rate,
            language=language,
        )
        part2 = await self._speech_service.generate_speech(
            text=script.part2,
            gender=script.resolved_gender,
            rate=speech_rate,
            language=language,
        )
        return AudioPair(part1=part1, part2=part2)

    async def generate_captions_pair(
        self,
        audio: AudioPair,
        script: StoryScript,
        language: Language = Language.PORTUGUESE,
    ) -> CaptionsPair:
        cap1 = await self._captions_service.generate_captions(
            audio_bytes=audio.part1.bytes,
            enhance_captions=True,
            language=language,
            base_text=script.part1,
        )
        cap2 = await self._captions_service.generate_captions(
            audio_bytes=audio.part2.bytes,
            enhance_captions=True,
            language=language,
            base_text=script.part2,
        )
        data1 = self._strip_introduction(
            [{"word": s.text, "start": s.start, "end": s.end}
             for s in cap1.captions.segments]
        )
        data2 = self._strip_introduction(
            [{"word": s.text, "start": s.start, "end": s.end}
             for s in cap2.captions.segments]
        )
        return CaptionsPair(part1=cap1, part2=cap2, part1_data=data1, part2_data=data2)

    async def generate_cover(
        self, post: RedditPost, script: StoryScript
    ) -> CoverResult:
        return await self._cover_service.generate_cover(
            RedditCover(
                title=script.title,
                community=post.community,
                author=post.author,
                image_url=post.community_url_photo,
            )
        )

    async def compose_two_part_video(
        self,
        audio: AudioPair,
        captions: CaptionsPair,
        cover: CoverResult,
        low_quality: bool = False,
    ) -> VideoPair:
        video_bytes_1 = await self._render_video_to_bytes(
            speech=audio.part1.clip,
            captions_clip_obj=captions.part1.clip,
            cover=cover.clip,
            low_quality=low_quality,
        )
        video_bytes_2 = await self._render_video_to_bytes(
            speech=audio.part2.clip,
            captions_clip_obj=captions.part2.clip,
            cover=cover.clip,
            low_quality=low_quality,
        )
        return VideoPair(part1_video=video_bytes_1, part2_video=video_bytes_2)

    async def generate_image_stories(
        self,
        script: StoryScript,
        captions: CaptionsPair,
    ) -> ImageStoryPair:
        """LLM plans timed image descriptions + prompts for both parts."""
        image_story_1 = await self._llm_proxy.generate_image_story(
            story_text=script.part1,
            transcription=captions.part1_data,
        )
        style_context = self._extract_style_context(image_story_1)
        image_story_2 = await self._llm_proxy.generate_image_story(
            story_text=script.part2,
            transcription=captions.part2_data,
            style_context=style_context,
        )
        config = self._video_service._video_config
        img_w, img_h = config.width, config.height

        generated_1 = self._generate_images_for_story(image_story_1, img_w, img_h)
        generated_2 = self._generate_images_for_story(image_story_2, img_w, img_h)

        return ImageStoryPair(
            part1=image_story_1,
            part2=image_story_2,
            generated_images_1=generated_1,
            generated_images_2=generated_2,
        )

    def compose_image_story_video(
        self,
        audio: AudioPair,
        captions: CaptionsPair,
        image_stories: ImageStoryPair,
        cover: CoverResult,
        low_quality: bool = False,
    ) -> VideoPair:
        video_bytes_1 = self._render_image_story_to_bytes(
            audio=audio.part1.clip,
            image_story=image_stories.part1,
            generated_images=image_stories.generated_images_1,
            cover=cover.clip,
            captions=captions.part1.clip,
            low_quality=low_quality,
        )
        video_bytes_2 = self._render_image_story_to_bytes(
            audio=audio.part2.clip,
            image_story=image_stories.part2,
            generated_images=image_stories.generated_images_2,
            cover=cover.clip,
            captions=captions.part2.clip,
            low_quality=low_quality,
        )
        return VideoPair(part1_video=video_bytes_1, part2_video=video_bytes_2)

    # ------------------------------------------------------------------
    # Public API (monolithic, kept for backward compat)
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
        """Full pipeline: scrape -> story -> speech -> captions -> videos."""

        post = self.scrape_post(post_url)
        original_post_md = f"# {post.title}\n\n{post.content}\n"

        script = await self.generate_script(post, language, speech_gender)
        audio = await self.generate_audio(script, speech_rate, language)
        captions = await self.generate_captions_pair(audio, script, language)
        cover = await self.generate_cover(post, script)
        videos = await self.compose_two_part_video(audio, captions, cover, low_quality)

        story_md = f"# {script.title}\n\n"
        story_md += f"**Narrator gender:** {script.narrator_gender} → resolved: {script.resolved_gender}\n\n"
        story_md += f"## Part 1\n\n{script.part1}\n\n"
        story_md += f"## Part 2\n\n{script.part2}\n"

        return TwoPartVideoResult(
            part1_video=videos.part1_video,
            part2_video=videos.part2_video,
            story_md=story_md,
            original_post_md=original_post_md,
            audio_part1=audio.part1.bytes,
            audio_part2=audio.part2.bytes,
            captions_part1_json=json.dumps(
                captions.part1_data, ensure_ascii=False, indent=2
            ),
            captions_part2_json=json.dumps(
                captions.part2_data, ensure_ascii=False, indent=2
            ),
            cover_png=cover.bytes,
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

        captions_1_data = self._strip_introduction(
            [
                {"word": s.text, "start": s.start, "end": s.end}
                for s in captions_result_1.captions.segments
            ]
        )
        captions_2_data = self._strip_introduction(
            [
                {"word": s.text, "start": s.start, "end": s.end}
                for s in captions_result_2.captions.segments
            ]
        )

        # 5. LLM: generate image stories from captions
        image_story_1 = await self._llm_proxy.generate_image_story(
            story_text=part1_text,
            transcription=captions_1_data,
        )

        style_context = self._extract_style_context(image_story_1)

        image_story_2 = await self._llm_proxy.generate_image_story(
            story_text=part2_text,
            transcription=captions_2_data,
            style_context=style_context,
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

    SFW_NEGATIVE_PROMPT = (
        "nsfw, nudity, sexual, gore, violence, blood, "
        "explicit, inappropriate, offensive"
    )

    @staticmethod
    def _strip_introduction(transcription: list[dict]) -> list[dict]:
        """Remove words up to and including 'Parte N.' from the transcription.

        The title and "Parte 1/2" are spoken at the beginning but shown as
        a cover image, so subtitles for them are redundant.
        """
        parte_idx = -1
        for i, w in enumerate(transcription):
            word = w.get("word", "").strip()
            if re.match(r"^\d+[.,]?$", word):
                prev = (
                    transcription[i - 1].get("word", "").strip().lower()
                    if i > 0
                    else ""
                )
                if prev in ("parte", "part"):
                    parte_idx = i
                    break
        if parte_idx >= 0:
            return transcription[parte_idx + 1 :]
        return transcription

    @staticmethod
    def _extract_style_context(image_story) -> str:
        """Build a style guide from part 1's image prompts so part 2 stays consistent."""
        prompts = [img.prompt for img in image_story.images[:5]]
        lines = [f"- Image {i + 1}: {p}" for i, p in enumerate(prompts)]
        return (
            "The following image prompts were used in Part 1. "
            "Reuse the exact same character descriptions (age, hair, build, clothing) "
            "and the exact same art style suffix for all prompts in Part 2.\n\n"
            + "\n".join(lines)
        )

    def _generate_images_for_story(self, image_story, width: int, height: int) -> list:
        generated = []
        for img_def in image_story.images:
            result = self._image_generation_proxy.generate_image(
                prompt=img_def.prompt,
                negative_prompt=self.SFW_NEGATIVE_PROMPT,
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
