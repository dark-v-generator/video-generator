from moviepy import editor
import random


class VideoClip:
    def __init__(self, file_path=None, audio_clip=None):
        self.clip = None if file_path == None else editor.VideoFileClip(file_path)
        if audio_clip:
            self.set_audio(audio_clip)

    def set_audio(self, audio_clip):
        self.audio_clip = audio_clip
        self.clip = self.clip.set_audio(audio_clip.clip)

    def concat(self, video_clip):
        if not self.clip:
            self.clip = video_clip.clip
        else:
            self.clip = editor.concatenate_videoclips([self.clip, video_clip.clip])

    def merge(self, video_clip):
        self.clip = editor.CompositeVideoClip([self.clip, video_clip.clip])

    def resize(self, width, height):
        original_aspect_ratio = self.clip.size[0] / self.clip.size[1]
        desired_aspect_ratio = width / height
        if original_aspect_ratio > desired_aspect_ratio:
            new_width = int(self.clip.size[1] * desired_aspect_ratio)
            margin = (self.clip.size[0] - new_width) / 2
            self.clip = self.clip.crop(x1=margin, x2=self.clip.size[0] - margin)
        elif original_aspect_ratio < desired_aspect_ratio:
            new_height = int(self.clip.size[0] / desired_aspect_ratio)
            margin = (self.clip.size[1] - new_height) / 2
            self.clip = self.clip.crop(y1=margin, y2=self.clip.size[1] - margin)
        self.clip = self.clip.resize(newsize=(width, height))

    def ajust_duration(self, duration):
        video_duration = self.clip.duration
        if duration > video_duration:
            repeats = int(-(-duration // video_duration))
            self.clip = self.clip.loop(n=repeats)
        elif duration < video_duration:
            start_time = random.uniform(0, video_duration - duration)
            self.clip = self.clip.subclip(start_time, start_time + duration)
