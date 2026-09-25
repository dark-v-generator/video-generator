import logging
from typing import Optional

from ..entities.configs.services.video import VideoConfig

from ..entities.editor import image_clip, audio_clip, video_clip, captions_clip

logger = logging.getLogger(__name__)


class VideoService:
    """Composes narration, footage, cover, CTA, watermark and captions."""

    def __init__(self, video_config: VideoConfig):
        self._video_config = video_config
        self._watermark_bytes = None
        if self._video_config.watermark_path:
            with open(self._video_config.watermark_path, "rb") as f:
                self._watermark_bytes = f.read()

        self._call_to_action_bytes = None
        if self._video_config.call_to_action_path:
            with open(self._video_config.call_to_action_path, "rb") as f:
                self._call_to_action_bytes = f.read()

    def generate_video(
        self,
        audio: audio_clip.AudioClip,
        background_video: video_clip.VideoClip,
        low_quality: bool = False,
        cover: Optional[image_clip.ImageClip] = None,
        captions: Optional[captions_clip.CaptionsClip] = None,
        cta_start: float = 0,
    ) -> video_clip.VideoClip:
        """Generate final video with all components.

        The narration runs from the first frame; the cover sits on top of it
        for ``cover_duration`` seconds. The cover is deliberately narrower
        than the frame and the captions sit below it, so the opening subtitles
        stay readable while it is up. When *cta_start* is positive the
        configured CTA image is composited at that time.
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

        audio.add_end_silence(config.end_silece_seconds)
        background_video.resize(config.width, config.height)
        background_video.ajust_duration(audio.clip.duration)
        background_video.set_audio(audio)

        width, height = background_video.clip.size
        total_duration = audio.clip.duration
        fade = self.CROSSFADE_DURATION

        # --- cover ---
        if cover is not None:
            cover.fit_width(int(width * config.cover_width_ratio))
            cover.center(width, height)
            cover_dur = float(config.cover_duration)
            cover.set_duration(cover_dur)
            cover.apply_fadeout(min(0.3, cover_dur))
            background_video.merge(cover)

        # --- CTA image overlay ---
        if (
            self._call_to_action_bytes is not None
            and cta_start > 0
            and cta_start < total_duration
        ):
            cta_clip = image_clip.ImageClip(bytes=self._call_to_action_bytes)
            cta_clip.fit_width(width, config.padding)
            cta_clip.center(width, height)
            cta_clip.set_start(cta_start)
            cta_clip.set_duration(total_duration - cta_start)
            cta_clip.apply_fadein(fade)
            background_video.merge(cta_clip)

        # --- watermark ---
        if self._watermark_bytes is not None:
            water_mark = image_clip.ImageClip(bytes=self._watermark_bytes)
            water_mark.fit_width(width, config.padding)
            water_mark.center(width, height)
            water_mark.set_duration(total_duration)
            background_video.merge(water_mark)

        # --- captions ---
        if captions is not None:
            background_video.insert_captions(captions, size_rate=size_rate)
        return background_video

    CROSSFADE_DURATION = 0.5
