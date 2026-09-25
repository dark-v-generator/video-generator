"""A narrated story over background footage, with cover, captions and CTA."""

import asyncio
import json
import os
import tempfile

from ...entities.captions import Captions
from ...entities.configs.services.video import VideoConfig
from ...entities.cover import RedditCover
from ...entities.rendered import RenderedPart
from ...entities.story import Story, StoryPart
from ..footage import FootageSource
from .captions import CaptionsService
from .censor import TextCensor
from .compose import VideoComposer
from .cover import CoverService
from .cta import compute_cta_start
from .speech import SpeechService


class NarrationOverFootageRenderer:
    """Renders each part as its narration over footage at least as long."""

    name = "narration-over-footage"

    def __init__(
        self,
        speech: SpeechService,
        captions: CaptionsService,
        cover: CoverService,
        footage: FootageSource,
        composer: VideoComposer,
        censor: TextCensor,
        video_config: VideoConfig,
    ) -> None:
        self._speech = speech
        self._captions = captions
        self._cover = cover
        self._footage = footage
        self._composer = composer
        self._censor = censor
        self._video_config = video_config

    async def render(
        self, story: Story, *, low_quality: bool = False
    ) -> list[RenderedPart]:
        return [
            await self._render_part(story, part, low_quality=low_quality)
            for part in story.parts
        ]

    async def _render_part(
        self, story: Story, part: StoryPart, *, low_quality: bool
    ) -> RenderedPart:
        speech = await self._speech.generate_speech(
            text=part.text,
            gender=story.resolved_gender,
            rate=1.0,
            language=story.language,
        )

        captions = await self._captions.generate_captions(
            audio_bytes=speech.bytes,
            enhance_captions=True,
            language=story.language,
            base_text=part.text,
        )
        words = [
            {"word": s.text, "start": s.start, "end": s.end}
            for s in captions.captions.segments
        ]
        cta_start = compute_cta_start(words)

        # The title is not narrated (it lives on the cover), so the whole
        # transcription is story content — nothing is trimmed. The cover gets
        # its own slot at the front of the video instead.
        censored_words = self._censor.censor_word_dicts(words)
        captions.clip.captions = Captions(
            segments=self._censor.censor_segments(captions.clip.captions.segments)
        )

        cover_title = self._censor.censor(story.cover_title_for(part))
        cover = await self._cover.generate_cover(
            RedditCover(
                title=cover_title,
                community=story.origin.community,
                author=story.origin.author,
                image_url=story.origin.community_image_url,
            )
        )

        footage = await self._footage.compile(
            min_duration=speech.clip.clip.duration, low_quality=low_quality
        )
        video = self._composer.compose(
            audio=speech.clip,
            background_video=footage.clip,
            low_quality=low_quality,
            cover=cover.clip,
            captions=captions.clip,
            cta_start=cta_start,
        )

        return RenderedPart(
            part=part,
            cover_title=cover_title,
            video=await asyncio.to_thread(self._write_mp4, video.clip),
            audio=speech.bytes,
            captions_json=json.dumps(censored_words, ensure_ascii=False, indent=2),
            cover_png=cover.bytes,
        )

    def _write_mp4(self, clip) -> bytes:
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            path = tmp.name
        try:
            clip.write_videofile(
                path,
                fps=self._video_config.fps,
                ffmpeg_params=self._video_config.ffmpeg_params,
            )
            with open(path, "rb") as f:
                return f.read()
        finally:
            os.unlink(path)
