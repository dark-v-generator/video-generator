import asyncio
import os
from tempfile import NamedTemporaryFile
from enum import Enum
from typing import Optional, List

from fish_audio_sdk import Session, TTSRequest

from ..core.config import settings

from ..repositories.interfaces import IConfigRepository

from .interfaces import ISpeechService
from ..entities.language import Language
from ..entities.config import MainConfig
from ..proxies import azure_proxy
from ..core.logging_config import get_logger
from ..entities.speech_voice import SpeechVoice


class CoquiSpeechService(ISpeechService):
    """Coqui TTS-based speech synthesis service implementation"""

    def __init__(self):
        """Initialize Coqui TTS model"""
        self._tts = None
        self._device = None

    async def _initialize_tts(self):
        """Lazy initialize TTS model"""
        if self._tts is None:
            try:
                import torch
                from TTS.api import TTS

                self._device = "cuda" if torch.cuda.is_available() else "cpu"
                # Using XTTS v2 for multilingual support
                loop = asyncio.get_event_loop()
                self._tts = await loop.run_in_executor(
                    None,
                    lambda: TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(
                        self._device
                    ),
                )
            except ImportError:
                raise ImportError(
                    "Coqui TTS not installed. Install with: pip install coqui-tts"
                )

    async def generate_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        rate: float = 1.0,
    ) -> bytes:
        """Generate speech from text using Coqui TTS with progress events"""
        await self._initialize_tts()
        # Convert language to Coqui format
        voice = self._get_voice_by_id(voice_id) if voice_id else self.list_voices()[0]
        lang_code = self._get_language_code(voice.language)
        loop = asyncio.get_event_loop()

        # Coqui has a limitation and it is used just for testing purposes
        text = text[:350]

        def run_tts():
            with NamedTemporaryFile(suffix=".wav") as temp_wav_file:
                # Generate speech to WAV file first
                self._tts.tts_to_file(
                    text=text,
                    language=lang_code,
                    file_path=temp_wav_file.name,
                    speed=rate,
                    speaker=voice.id,
                )

                # Convert WAV to MP3 using pydub
                from pydub import AudioSegment
                import os

                # Configure ffmpeg path if available
                ffmpeg_path = os.environ.get("FFMPEG_PATH")
                if ffmpeg_path:
                    AudioSegment.converter = ffmpeg_path
                    AudioSegment.ffmpeg = ffmpeg_path
                    AudioSegment.ffprobe = ffmpeg_path.replace("ffmpeg", "ffprobe")

                # Load WAV and convert to MP3
                audio = AudioSegment.from_wav(temp_wav_file.name)

                # Export to temporary MP3 file and read bytes
                with NamedTemporaryFile(suffix=".mp3") as temp_mp3_file:
                    audio.export(temp_mp3_file.name, format="mp3", bitrate="128k")

                    # Read the MP3 file
                    with open(temp_mp3_file.name, "rb") as f:
                        return f.read()

        audio_bytes = await loop.run_in_executor(None, run_tts)
        return audio_bytes

    def list_voices(self) -> List[SpeechVoice]:
        """List all available voices"""
        return [
            SpeechVoice(
                id="Luis Moray",
                name="Luis Moray",
                image_url="https://i.imgur.com/gv7oZgj.jpeg",
                language=Language.ENGLISH,
            ),
            SpeechVoice(
                id="Ana Florence",
                name="Ana Florence",
                image_url="https://i.imgur.com/gv7oZgj.jpeg",
                language=Language.PORTUGUESE,
            ),
            SpeechVoice(
                id="Andrew Chipper",
                name="Andrew Chipper",
                image_url="https://i.imgur.com/gv7oZgj.jpeg",
                language=Language.PORTUGUESE,
            ),
            SpeechVoice(
                id="Claribel Dervla",
                name="Claribel Dervla",
                image_url="https://i.imgur.com/gv7oZgj.jpeg",
                language=Language.ENGLISH,
            ),
        ]

    def _get_voice_by_id(self, id: str) -> Optional[SpeechVoice]:
        """Get voice by id"""
        return next((voice for voice in self.list_voices() if voice.id == id), None)

    def _get_language_code(self, language: Language) -> str:
        """Get language code for Coqui TTS"""
        match language:
            case Language.PORTUGUESE:
                return "pt"
            case Language.ENGLISH:
                return "en"
            case _:
                return "pt"


class FishSpeechService(ISpeechService):
    """FishAudio SDK-based TTS implementation"""

    def __init__(self):
        self._logger = get_logger(__name__)
        # API key resolution: env takes precedence
        self._api_key = settings.fish_audio_api_key

    async def generate_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        rate: float = 1.0,
    ) -> bytes:
        """Generate speech using FishAudio SDK.

        Authentication is done via FISH_AUDIO_API_KEY env or config.speech_config.fish_audio_api_key.
        """

        voice = self._get_voice_by_id(voice_id) if voice_id else self.list_voices()[0]

        audio_chunks: list[bytes] = []
        session = self._get_session()
        for chunk in session.tts(
            TTSRequest(
                reference_id=voice.id,
                text=text,
                format="mp3",
                normalize=False,
            ),
            backend="s1",
        ):
            audio_chunks.append(chunk)
        return b"".join(audio_chunks)

    def _get_session(self) -> Session:
        return Session(self._api_key)  # Using this to lazy load the SDK

    def _get_voice_by_id(self, id: str) -> Optional[SpeechVoice]:
        """Get voice by id"""
        return next((voice for voice in self.list_voices() if voice.id == id), None)

    def list_voices(self) -> List[SpeechVoice]:
        return [
            SpeechVoice(
                id="b9e8d9d645a347a98535493f2df97b3c",
                name="Modelo 1",
                image_url="https://public-platform.r2.fish.audio/cdn-cgi/image/width=128,format=webp/coverimage/1d8cb595b6284ff7aa7e8fec7b93249d",
                language=Language.PORTUGUESE,
            ),
            SpeechVoice(
                id="1573caa3d6444e16a28eab1f094e1416",
                name="Modelo 2",
                image_url="https://public-platform.r2.fish.audio/cdn-cgi/image/width=128,format=webp/coverimage/1573caa3d6444e16a28eab1f094e1416",
                language=Language.PORTUGUESE,
            ),
            SpeechVoice(
                id="7fe10a00249247aabb495bae57ac80e1",
                name="Galvão Bueno",
                image_url="https://public-platform.r2.fish.audio/cdn-cgi/image/width=128,format=webp/coverimage/7fe10a00249247aabb495bae57ac80e1",
                language=Language.PORTUGUESE,
            ),
            SpeechVoice(
                id="1a61293f8fa8441f804deb10d0b2bc95",
                name="Adam",
                image_url="https://fish.audio/_next/image/?url=https%3A%2F%2Fpublic-platform.r2.fish.audio%2Fcoverimage%2F1a61293f8fa8441f804deb10d0b2bc95&w=128&q=75",
                language=Language.PORTUGUESE,
            ),
        ]


class SpeechServiceFactory:
    """Factory to create speech services based on configuration"""

    @staticmethod
    def create_speech_service(config_repository: IConfigRepository) -> ISpeechService:
        logger = get_logger(__name__)
        """Create appropriate speech service based on provider name or configuration"""
        config = config_repository.load_config()
        provider = config.speech_config.provider
        if provider is None:
            provider = MainConfig().speech_config.provider  # Default provider

        if provider is not None and config is not None:
            provider = config.speech_config.provider

        provider = provider.lower().strip()
        logger.info(f"Creating speech service for provider: {provider}")
        if provider == "coqui":
            return CoquiSpeechService()
        elif provider == "fish-speech" or provider == "fish_speech":
            return FishSpeechService()
        else:
            # Default to Azure
            return CoquiSpeechService()
