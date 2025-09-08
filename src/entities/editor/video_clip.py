import tempfile
from moviepy import (
    VideoClip as MoviepyVideoClip,
    VideoFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
)
import random

from src.entities.editor.captions_clip import CaptionsClip


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

    def insert_captions(self, captions: CaptionsClip):
        self.clip = CompositeVideoClip([self.clip, *captions.clips])

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
            start_time = random.uniform(0, video_duration - duration)
            self.clip = self.clip.subclipped(start_time, start_time + duration)
