from io import BytesIO
from typing import Optional
from openai import OpenAI
from src.adapters.proxies.interfaces import ITranscriptionProxy
from src.entities.language import Language
from src.entities.transcription import TranscriptionResult, TranscriptionWord
from src.entities.configs.transcription import OpenAITranscriptionConfig
from src.core.logging_config import get_logger


class OpenAIWhisperProxy(ITranscriptionProxy):
    def __init__(self, config: OpenAITranscriptionConfig):
        self.logger = get_logger(__name__)
        api_key = config.api_key
        if not api_key:
            raise ValueError("OpenAI API key not provided")

        self.model_id = config.model
        self.client = OpenAI(api_key=api_key)

    def transcribe(
        self, audio_bytes: bytes, language: Optional[Language] = None
    ) -> TranscriptionResult:
        audio_stream = BytesIO(audio_bytes)
        audio_stream.name = "audio.mp3"

        kwargs = {
            "model": self.model_id,
            "response_format": "verbose_json",
            "timestamp_granularities": ["word"],
        }
        if language:
            kwargs["language"] = language.value

        transcription = self.client.audio.transcriptions.create(
            file=audio_stream, **kwargs
        )

        transcription_dict = transcription.model_dump()

        transcription_words = []
        for word_data in transcription_dict.get("words", []):
            transcription_words.append(
                TranscriptionWord(
                    word=word_data["word"],
                    start=word_data["start"],
                    end=word_data["end"],
                )
            )

        return TranscriptionResult(
            text=transcription_dict.get("text", ""),
            words=transcription_words,
            language=transcription_dict.get("language"),
        )
