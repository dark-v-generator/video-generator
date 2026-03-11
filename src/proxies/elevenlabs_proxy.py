import requests
from typing import Literal, Optional
from src.proxies.interfaces import ISpeechProxy
from src.entities.configs.proxies.speech import ElevenLabsSpeechConfig
from src.entities.language import Language
from src.core.logging_config import get_logger


class ElevenLabsSpeechProxy(ISpeechProxy):
    def __init__(self, config: ElevenLabsSpeechConfig):
        self.logger = get_logger(__name__)
        self.config = config
        self.api_key = config.api_key

        if not self.api_key:
            raise ValueError("ElevenLabs API key is not set")

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
            # Fallback default elevenlabs ids
            return "pNInz6obbf5AWCG1OKVK"  # generic default voice (Adam)

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

        voice_id = self._get_voice_id(gender, language, override_voice_id)

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.api_key,
        }

        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5,
                # Note: API does not strictly have 'rate' parameter natively in voice_settings
                # We can adjust speaking_rate in v2 via different models or tags,
                # but ignoring it for basic generation.
            },
        }

        response = requests.post(url, json=data, headers=headers)

        if response.status_code != 200:
            raise Exception(
                f"ElevenLabs API Error: {response.status_code} - {response.text}"
            )

        return response.content

    def list_voices(self) -> list:
        from src.entities.speech_voice import SpeechVoice

        return [
            SpeechVoice(
                id="pNInz6obbf5AWCG1OKVK",
                name="Adam (M)",
                image_url="",
                language=Language.ENGLISH,
            )
        ]
