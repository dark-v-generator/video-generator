import tempfile
from entities.captions import Captions
from proxies import whisper_proxy

from services import speech_service

def generate_captions_from_file(audio_path: str) -> Captions:
    return whisper_proxy.generate_captions(audio_path)

def generate_captions_from_speech(text: str, gender: str, rate: float):
    tmp_mp3_path = f"{tempfile.mktemp()}.mp3"
    speech_service.synthesize_speech(text, gender, rate=1.0, output_path=tmp_mp3_path)
    captions = generate_captions_from_file(tmp_mp3_path)
    return captions.with_speed(rate)