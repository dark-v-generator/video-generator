from moviepy import editor
import os
from moviepy.audio.AudioClip import AudioArrayClip
import numpy as np

class AudioClip:
    def __init__(self, file_path, volume=1):
        if not os.path.isfile(file_path):
            raise Exception("O arquivo de áudio não existe.")

        self.clip = editor.AudioFileClip(file_path)
        self.clip = self.clip.volumex(volume)

    def add_end_silence(self, duration_in_seconds):
        silence = AudioArrayClip(np.zeros((44100 * duration_in_seconds, 2)), fps=44100)
        self.clip = editor.concatenate_audioclips([self.clip, silence])
    
    def ajust_duration(self, duration):
        if duration > self.clip.duration:
            repeats = int(-(-duration // self.clip.duration))
            clips = [self.clip] * repeats
            self.clip = editor.concatenate_audioclips(clips).subclip(0, duration)
        elif duration < self.clip.duration:
            self.clip = self.clip.subclip(0, duration)
    
    def merge(self, other_clip):
        other_clip.ajust_duration(self.clip.duration)
        self.clip = editor.CompositeAudioClip([self.clip, other_clip.clip])
