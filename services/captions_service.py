from entities.captions import Captions
from proxies import whisper_proxy


def generate_captions_from_file(audio_path: str) -> Captions:
    return whisper_proxy.generate_captions(audio_path)
