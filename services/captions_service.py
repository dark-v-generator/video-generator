from entities.captions import Captions
from entities.language import Language
from proxies import whisper_proxy


def generate_captions_from_file(audio_path: str, language: Language = Language.PORTUGUESE) -> Captions:
    return whisper_proxy.generate_captions(audio_path, language=language)
