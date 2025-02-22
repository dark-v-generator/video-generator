from moviepy import (
    AudioFileClip,
    CompositeAudioClip,
    AudioArrayClip,
    concatenate_audioclips,
    AudioClip as MoviepyAudioClip,
)
import numpy as np


class AudioClip:
    clip: MoviepyAudioClip

    def __init__(self, file_path, volume=1):
        self.file_path = file_path
        self.clip = AudioFileClip(file_path)
        self.clip = self.clip.with_volume_scaled(volume)

    def add_end_silence(self, duration_in_seconds):
        silence = AudioArrayClip(
            np.zeros((44100 * duration_in_seconds, 2)),
            fps=44100,
        )
        self.clip = concatenate_audioclips([self.clip, silence])

    def ajust_duration(self, duration):
        if duration > self.clip.duration:
            repeats = int(-(-duration // self.clip.duration))
            clips = [self.clip] * repeats
            self.clip = concatenate_audioclips(clips)[0:duration]
        elif duration < self.clip.duration:
            self.clip = self.clip[0:duration]

    def merge(self, other_clip: "AudioClip"):
        other_clip.ajust_duration(self.clip.duration)
        self.clip = CompositeAudioClip([self.clip, other_clip.clip])
