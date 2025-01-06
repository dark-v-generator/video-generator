from moviepy import editor
import os
from moviepy.audio.AudioClip import AudioArrayClip
import numpy as np
from io import BytesIO
import tempfile

class AudioClip:
    def __init__(self, source, volume=1):
        if isinstance(source, str):
            if not os.path.isfile(source):
                raise Exception("O arquivo de áudio não existe.")
            self.clip = editor.AudioFileClip(source)
        elif isinstance(source, BytesIO):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                temp_file.write(source.read())
                temp_file_path = temp_file.name
            self.clip = editor.AudioFileClip(temp_file_path)
            os.remove(temp_file_path)
        else:
            raise Exception("Fonte de áudio inválida. Deve ser um caminho de arquivo ou um stream.")
        
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