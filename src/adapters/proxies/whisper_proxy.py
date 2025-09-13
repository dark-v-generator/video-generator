import whisper
from ...adapters.proxies.interfaces import IWhisperProxy
from ...entities.captions import CaptionSegment, Captions
from ...entities.language import Language
from ...core.logging_config import get_logger


class LocalWhisperProxy(IWhisperProxy):
    def __init__(self):
        self.logger = get_logger(__name__)
        self.model = whisper.load_model("base")

    def generate_captions(
        self, audio_path: str, language: Language = Language.PORTUGUESE
    ) -> Captions:
        output = self.model.transcribe(
            audio_path, word_timestamps=True, language=language.value
        )

        caption_segments = []
        for segment in output["segments"]:
            for word in segment["words"]:
                caption_segments.append(
                    CaptionSegment(
                        start=word["start"],
                        end=word["end"],
                        text=word["word"],
                    )
                )
        return Captions(segments=caption_segments)
