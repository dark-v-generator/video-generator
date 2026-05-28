import random
import tempfile

import numpy as np
from moviepy import (
    VideoClip as MoviepyVideoClip,
    VideoFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
)
from moviepy.video.fx import (
    LumContrast,
    MirrorX,
    MultiplyColor,
    MultiplySpeed,
)
from PIL import Image

from src.entities.editor.captions_clip import CaptionsClip
from src.entities.configs.services.video import AntiFingerprintConfig


class VideoClip:
    clip: MoviepyVideoClip

    def __init__(self, file_path=None, audio_clip=None, bytes=None):
        if bytes:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmpfile:
                tmpfile.write(bytes)
                tmpfile.seek(0)
                self.clip = VideoFileClip(tmpfile.name)
        else:
            self.clip = None if file_path == None else VideoFileClip(file_path)
            if audio_clip:
                self.set_audio(audio_clip)

    def set_audio(self, audio_clip):
        self.audio_clip = audio_clip
        self.clip = self.clip.with_audio(audio_clip.clip)

    def concat(self, video_clip):
        if not self.clip:
            self.clip = video_clip.clip
        else:
            self.clip = concatenate_videoclips([self.clip, video_clip.clip])

    def merge(self, video_clip):
        self.clip = CompositeVideoClip([self.clip, video_clip.clip])

    def insert_captions(self, captions: CaptionsClip, size_rate: float = 1.0):
        self.clip = CompositeVideoClip([self.clip, *captions.get_clips(size_rate)])

    def resize(self, width, height):
        original_aspect_ratio = self.clip.size[0] / self.clip.size[1]
        desired_aspect_ratio = width / height
        if original_aspect_ratio > desired_aspect_ratio:
            new_width = int(self.clip.size[1] * desired_aspect_ratio)
            margin = (self.clip.size[0] - new_width) / 2
            self.clip = self.clip.cropped(x1=margin, x2=self.clip.size[0] - margin)
        elif original_aspect_ratio < desired_aspect_ratio:
            new_height = int(self.clip.size[0] / desired_aspect_ratio)
            margin = (self.clip.size[1] - new_height) / 2
            self.clip = self.clip.cropped(y1=margin, y2=self.clip.size[1] - margin)
        self.clip = self.clip.resized(new_size=(width, height))

    def ajust_duration(self, duration):
        video_duration = self.clip.duration
        if duration > video_duration:
            repeats = int(-(-duration // video_duration))
            self.clip = self.clip * repeats
        elif duration < video_duration:
            self.clip = self.clip.subclipped(0, duration)

    def apply_anti_fingerprint(self, config: AntiFingerprintConfig) -> None:
        """Apply randomized geometric/color/speed jitter to evade fingerprinting.

        Should be called before the clip's audio is replaced. Speed changes
        also rescale the audio track, but the pipeline replaces audio with
        the TTS narration further downstream, so any pitch shift is dropped.
        """
        if not config.enabled or self.clip is None:
            return

        if config.zoom > 1.0:
            ow, oh = self.clip.size
            zoomed = self.clip.resized(config.zoom)
            zw, zh = zoomed.size
            x1 = (zw - ow) // 2
            y1 = (zh - oh) // 2
            self.clip = zoomed.cropped(x1=x1, y1=y1, x2=x1 + ow, y2=y1 + oh)

        effects = []
        if config.mirror:
            effects.append(MirrorX())
        if config.brightness_delta > 0:
            factor = 1.0 + random.uniform(
                -config.brightness_delta, config.brightness_delta
            )
            effects.append(MultiplyColor(factor))
        if config.contrast_delta > 0:
            contrast = random.uniform(-config.contrast_delta, config.contrast_delta)
            effects.append(LumContrast(contrast=contrast))
        if config.speed_delta > 0:
            speed = 1.0 + random.uniform(-config.speed_delta, config.speed_delta)
            effects.append(MultiplySpeed(speed))

        if effects:
            self.clip = self.clip.with_effects(effects)

        if config.hue_shift_degrees > 0:
            shift = random.uniform(
                -config.hue_shift_degrees, config.hue_shift_degrees
            )
            self.clip = _apply_hue_shift(self.clip, shift)


def _apply_hue_shift(clip: MoviepyVideoClip, degrees: float) -> MoviepyVideoClip:
    """Rotate the hue channel of every frame by ``degrees``.

    Implemented in HSV space via PIL. Saturation and luminance are left
    untouched, which yields the most natural-looking shift.
    """
    offset = int(round(degrees / 360.0 * 256.0)) % 256

    def shift(frame: np.ndarray) -> np.ndarray:
        pil = Image.fromarray(frame, mode="RGB").convert("HSV")
        h, s, v = pil.split()
        h_shifted = (np.array(h, dtype=np.int16) + offset) % 256
        h_new = Image.fromarray(h_shifted.astype(np.uint8), mode="L")
        return np.array(Image.merge("HSV", (h_new, s, v)).convert("RGB"))

    return clip.image_transform(shift)
