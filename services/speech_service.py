from proxies import polly_proxy
from entities.editor import audio_clip

def synthesize_speech(text: str) -> audio_clip.AudioClip:
    stream = polly_proxy.synthesize_speech(text)
    return audio_clip.AudioClip(stream)