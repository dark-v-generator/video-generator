import os
import tempfile
import whisper
from typing import Optional
from src.adapters.proxies.interfaces import ITranscriptionProxy
from src.entities.language import Language
from src.entities.transcription import TranscriptionResult, TranscriptionWord
from src.entities.configs.transcription import LocalTranscriptionConfig
from src.core.logging_config import get_logger


class LocalWhisperProxy(ITranscriptionProxy):
    def __init__(self, config: LocalTranscriptionConfig):
        self.logger = get_logger(__name__)
        self.model = whisper.load_model(config.model)

    def transcribe(
        self, audio_bytes: bytes, language: Optional[Language] = None
    ) -> TranscriptionResult:
        # Local whisper requires a file path, so write bytes to a temp file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
            temp_audio.write(audio_bytes)
            temp_path = temp_audio.name

        try:
            kwargs = {"word_timestamps": True}
            if language:
                kwargs["language"] = language.value

            output = self.model.transcribe(temp_path, **kwargs)

            transcription_words = []
            for segment in output.get("segments", []):
                for word_data in segment.get("words", []):
                    transcription_words.append(
                        TranscriptionWord(
                            word=word_data["word"],
                            start=word_data["start"],
                            end=word_data["end"],
                            probability=word_data.get("probability"),
                        )
                    )

            return TranscriptionResult(
                text=output.get("text", ""),
                words=transcription_words,
                language=output.get("language"),
            )
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
