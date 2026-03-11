from dataclasses import dataclass
from typing import Literal, Optional

from ..adapters.proxies.interfaces import ISpeechProxy
from ..entities.editor.audio_clip import AudioClip
from ..entities.language import Language
from ..core.logging_config import get_logger


@dataclass
class SpeechResult:
    clip: AudioClip
    bytes: bytes


class SpeechService:
    """Speech generation service that returns a SpeechResult"""

    def __init__(self, speech_proxy: ISpeechProxy):
        self._speech_proxy = speech_proxy
        self._logger = get_logger(__name__)

    async def generate_speech(
        self,
        text: str,
        gender: Literal["male", "female"] = "male",
        rate: float = 1.0,
        language: Language = Language.PORTUGUESE,
        override_voice_id: Optional[str] = None,
    ) -> SpeechResult:
        """Generate speech from text and return a SpeechResult"""
        self._logger.info(
            "Generating speech: %d chars, gender=%s, rate=%s",
            len(text),
            gender,
            rate,
        )
        speech_bytes = await self._speech_proxy.generate_speech(
            text=text,
            gender=gender,
            rate=rate,
            language=language,
            override_voice_id=override_voice_id,
        )
        clip = AudioClip(bytes=speech_bytes)
        return SpeechResult(clip=clip, bytes=speech_bytes)
