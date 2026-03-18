import io
import random
from dataclasses import dataclass
from typing import Optional, List

import numpy as np
from moviepy import CompositeVideoClip, VideoClip as MoviepyVideoClip
from moviepy.video.fx import CrossFadeIn
from PIL import Image, ImageFilter

from ..proxies.interfaces import IYouTubeProxy
from ..entities.configs.services.video import VideoConfig
from ..entities.image_story import ImageStory

from ..entities.editor import image_clip, audio_clip, video_clip, captions_clip


@dataclass
class YouTubeCompilationResult:
    clip: video_clip.VideoClip
    downloaded_bytes: List[bytes]


class VideoService:
    """Video generation service implementation"""

    def __init__(
        self,
        youtube_proxy: IYouTubeProxy,
        video_config: VideoConfig,
    ):
        self._youtube_proxy = youtube_proxy
        self._video_config = video_config
        self._watermark_bytes = None
        if self._video_config.watermark_path:
            with open(self._video_config.watermark_path, "rb") as f:
                self._watermark_bytes = f.read()

        self._call_to_action_bytes = None
        if self._video_config.call_to_action_path:
            with open(self._video_config.call_to_action_path, "rb") as f:
                self._call_to_action_bytes = f.read()

    async def create_youtube_video_compilation(
        self, min_duration: int, low_quality: bool = False
    ) -> YouTubeCompilationResult:
        """Create video compilation from YouTube content"""

        video_ids = await self._youtube_proxy.list_video_ids(
            self._video_config.youtube_channel_url
        )
        random.shuffle(video_ids)

        video = video_clip.VideoClip()
        downloaded_bytes: List[bytes] = []
        total_duration = 0
        processed_videos = 0
        total_videos_to_process = min(len(video_ids), 2)

        for video_id in video_ids[:total_videos_to_process]:
            video_bytes = await self._youtube_proxy.download_video(
                video_id, low_quality
            )
            downloaded_bytes.append(video_bytes)

            new_video = video_clip.VideoClip(bytes=video_bytes)
            video.concat(new_video)
            total_duration += new_video.clip.duration
            processed_videos += 1

            if total_duration >= min_duration:
                return YouTubeCompilationResult(
                    clip=video, downloaded_bytes=downloaded_bytes
                )
        if total_duration < min_duration:
            raise Exception(
                f"Video compilation completed with {total_duration:.1f}s duration (all available videos used)"
            )
        return YouTubeCompilationResult(clip=video, downloaded_bytes=downloaded_bytes)

    def generate_video(
        self,
        audio: audio_clip.AudioClip,
        background_video: video_clip.VideoClip,
        low_quality: bool = False,
        cover: Optional[image_clip.ImageClip] = None,
        captions: Optional[captions_clip.CaptionsClip] = None,
    ) -> video_clip.VideoClip:
        """Generate final video with all components"""
        config = self._video_config
        size_rate = 1.0
        # Downscale config for preview natively inside VideoService
        if low_quality:
            size_rate = 400 / config.height
            config = config.model_copy(
                update=dict(
                    width=int(round(config.width * size_rate)),
                    height=int(round(config.height * size_rate)),
                    padding=int(round(config.padding * size_rate)),
                )
            )

        audio.add_end_silence(config.end_silece_seconds)
        background_video.resize(config.width, config.height)
        background_video.ajust_duration(audio.clip.duration)
        background_video.set_audio(audio)

        width, height = background_video.clip.size

        if cover is not None:
            cover.fit_width(width, config.padding)
            cover.center(width, height)
            cover.set_duration(config.cover_duration)
            cover.apply_fadeout(1)
            background_video.merge(cover)
        if self._watermark_bytes is not None:
            water_mark = image_clip.ImageClip(bytes=self._watermark_bytes)
            water_mark.fit_width(width, config.padding)
            water_mark.center(width, height)
            water_mark.set_duration(audio.clip.duration)
            background_video.merge(water_mark)
        if captions is not None:
            background_video.insert_captions(captions, size_rate=size_rate)
        return background_video

    CROSSFADE_DURATION = 0.5
    KEN_BURNS_MAX_SCALE = 1.12

    def generate_image_story_video(
        self,
        audio: audio_clip.AudioClip,
        image_story: ImageStory,
        generated_images: List[bytes],
        cover: Optional[image_clip.ImageClip] = None,
        captions: Optional[captions_clip.CaptionsClip] = None,
        low_quality: bool = False,
    ) -> video_clip.VideoClip:
        """Generate a video from a timed sequence of AI-generated images.

        The video has three phases:
        1. Introduction: first image is blurred with cover overlay on top.
           At introduction_end_time the image unblurs and cover fades out.
        2. Story: images appear at their scheduled times filling the background.
           Ken Burns zoom + crossfade transitions between images.
        3. Call-to-action: the active image blurs and a CTA overlay appears.
        """
        config = self._video_config
        size_rate = 1.0
        if low_quality:
            size_rate = 400 / config.height
            config = config.model_copy(
                update=dict(
                    width=int(round(config.width * size_rate)),
                    height=int(round(config.height * size_rate)),
                    padding=int(round(config.padding * size_rate)),
                )
            )

        width, height = config.width, config.height
        audio.add_end_silence(config.end_silece_seconds)
        total_duration = audio.clip.duration

        intro_end = image_story.introduction_end_time
        cta_start = image_story.call_to_action_start_time

        segments = self._build_image_segments(
            image_story, generated_images, total_duration, intro_end, cta_start
        )

        fade = self.CROSSFADE_DURATION
        moviepy_clips = []
        for idx, (start, end, img_bytes, is_blurred) in enumerate(segments):
            extended_end = (
                min(end + fade, total_duration) if idx < len(segments) - 1 else end
            )
            clip_duration = extended_end - start

            if is_blurred:
                img_bytes = self._blur_image_bytes(img_bytes)
                clip = image_clip.ImageClip(bytes=img_bytes)
                clip.clip = clip.clip.resized(new_size=(width, height))
                clip.set_start(start)
                clip.set_duration(clip_duration)
                moviepy_clips.append(clip.clip)
            else:
                zoom_in = random.choice([True, False])
                kb_clip = self._create_ken_burns_clip(
                    img_bytes, width, height, clip_duration, zoom_in
                )
                kb_clip = kb_clip.with_start(start)
                if start > 0:
                    kb_clip = CrossFadeIn(duration=fade).apply(kb_clip)
                moviepy_clips.append(kb_clip)

        if cover is not None and intro_end > 0:
            cover.fit_width(width, config.padding)
            cover.center(width, height)
            cover.set_start(0)
            cover.set_duration(intro_end)
            cover.apply_fadeout(1)
            moviepy_clips.append(cover.clip)

        if self._call_to_action_bytes is not None and cta_start < total_duration:
            cta_clip = image_clip.ImageClip(bytes=self._call_to_action_bytes)
            cta_clip.fit_width(width, config.padding)
            cta_clip.center(width, height)
            cta_clip.set_start(cta_start)
            cta_clip.set_duration(total_duration - cta_start)
            cta_clip.apply_fadein(fade)
            moviepy_clips.append(cta_clip.clip)

        result = video_clip.VideoClip()
        result.clip = CompositeVideoClip(moviepy_clips, size=(width, height))
        result.clip = result.clip.with_duration(total_duration)
        result.clip = result.clip.with_audio(audio.clip)

        if self._watermark_bytes is not None:
            water_mark = image_clip.ImageClip(bytes=self._watermark_bytes)
            water_mark.fit_width(width, config.padding)
            water_mark.center(width, height)
            water_mark.set_duration(total_duration)
            result.merge(water_mark)

        if captions is not None:
            result.insert_captions(captions, size_rate=size_rate)

        return result

    @staticmethod
    def _build_image_segments(
        image_story: ImageStory,
        generated_images: List[bytes],
        total_duration: float,
        intro_end: float,
        cta_start: float,
    ) -> List[tuple]:
        """Return (start, end, image_bytes, is_blurred) segments."""
        segments: List[tuple] = []
        images = image_story.images

        for i, (story_img, img_bytes) in enumerate(zip(images, generated_images)):
            img_start = story_img.start_time
            img_end = (
                images[i + 1].start_time if i + 1 < len(images) else total_duration
            )
            if img_end <= img_start:
                continue

            if i == 0 and intro_end > img_start:
                blur_end = min(intro_end, img_end)
                segments.append((img_start, blur_end, img_bytes, True))
                if intro_end < img_end:
                    img_start = intro_end
                else:
                    continue

            if img_start < cta_start < img_end:
                segments.append((img_start, cta_start, img_bytes, False))
                segments.append((cta_start, img_end, img_bytes, True))
            elif img_start >= cta_start:
                segments.append((img_start, img_end, img_bytes, True))
            else:
                segments.append((img_start, img_end, img_bytes, False))

        return segments

    @classmethod
    def _create_ken_burns_clip(
        cls, img_bytes: bytes, width: int, height: int, duration: float, zoom_in: bool
    ) -> MoviepyVideoClip:
        max_s = cls.KEN_BURNS_MAX_SCALE
        img = Image.open(io.BytesIO(img_bytes)).resize(
            (int(width * max_s), int(height * max_s)), Image.LANCZOS
        )
        img_array = np.array(img)
        base_h, base_w = img_array.shape[:2]

        def make_frame(t):
            progress = t / max(duration, 0.001)
            if zoom_in:
                scale = max_s - (max_s - 1.0) * progress
            else:
                scale = 1.0 + (max_s - 1.0) * progress
            crop_w = int(width * scale)
            crop_h = int(height * scale)
            x = (base_w - crop_w) // 2
            y = (base_h - crop_h) // 2
            cropped = img_array[y : y + crop_h, x : x + crop_w]
            return np.array(
                Image.fromarray(cropped).resize((width, height), Image.LANCZOS)
            )

        return MoviepyVideoClip(make_frame, duration=duration)

    @staticmethod
    def _blur_image_bytes(img_bytes: bytes, radius: int = 20) -> bytes:
        img = Image.open(io.BytesIO(img_bytes))
        blurred = img.filter(ImageFilter.GaussianBlur(radius=radius))
        buf = io.BytesIO()
        blurred.save(buf, format="PNG")
        return buf.getvalue()
