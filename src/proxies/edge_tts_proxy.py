from typing import Literal, Optional
from src.proxies.interfaces import ISpeechProxy
from src.entities.configs.speech import EdgeTTSSpeechConfig
from src.entities.language import Language
from src.core.logging_config import get_logger


class EdgeTTSSpeechProxy(ISpeechProxy):
    def __init__(self, config: EdgeTTSSpeechConfig):
        self.logger = get_logger(__name__)
        self.config = config

    def _get_voice_id(
        self,
        gender: Literal["male", "female"],
        language: Language,
        override_voice_id: Optional[str] = None,
    ) -> str:
        if override_voice_id:
            return override_voice_id

        voice_config = self.config.voices.get(language)
        if not voice_config:
            # Fallback default if not in config
            if language == Language.PORTUGUESE:
                return (
                    "pt-BR-AntonioNeural"
                    if gender == "male"
                    else "pt-BR-FranciscaNeural"
                )
            return "en-US-ChristopherNeural" if gender == "male" else "en-US-AriaNeural"

        return (
            voice_config.male_voice_id
            if gender == "male"
            else voice_config.female_voice_id
        )

    async def generate_speech(
        self,
        text: str,
        gender: Literal["male", "female"] = "male",
        rate: float = 1.0,
        language: Language = Language.PORTUGUESE,
        override_voice_id: Optional[str] = None,
    ) -> bytes:
        import edge_tts

        voice_id = self._get_voice_id(gender, language, override_voice_id)

        # Edge TTS rate takes string format e.g. "+0%" or "+50%"
        rate_percent = int((rate - 1.0) * 100)
        rate_str = f"+{rate_percent}%" if rate_percent >= 0 else f"{rate_percent}%"

        communicate = edge_tts.Communicate(text=text, voice=voice_id, rate=rate_str)

        audio_data = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data.extend(chunk["data"])

        return bytes(audio_data)

    def list_voices(self) -> list:
        from src.entities.speech_voice import SpeechVoice

        return [
            SpeechVoice(
                id="pt-BR-AntonioNeural",
                name="Antônio (M)",
                image_url="",
                language=Language.PORTUGUESE,
            ),
            SpeechVoice(
                id="pt-BR-FranciscaNeural",
                name="Francisca (F)",
                image_url="",
                language=Language.PORTUGUESE,
            ),
        ]
