import asyncio
import os
import tempfile

from ..services.llm.interfaces import ILLMService

from .interfaces import ICaptionsService
from ..repositories.interfaces import IFileStorage
from ..entities.captions import Captions
from ..entities.language import Language
from ..proxies import whisper_proxy
from ..entities.history import History
from ..core.logging_config import get_logger


class CaptionsService(ICaptionsService):
    """Captions generation service implementation"""

    def __init__(self, file_storage: IFileStorage, llm_service: ILLMService):
        self._file_storage = file_storage
        self._llm_service = llm_service
        self._logger = get_logger(__name__)

    async def generate_captions(
        self,
        audio_file_id: str,
        enhance_captions: bool = False,
        language: Language = Language.PORTUGUESE,
    ) -> Captions:
        """Generate captions from audio path; download to temp file; optionally enhance via LLM"""
        audio_bytes = self._file_storage.load_file(audio_file_id)
        if audio_bytes is None:
            raise Exception("Audio file not found")
        with tempfile.NamedTemporaryFile(suffix=".mp3") as tmpfile:
            tmpfile.write(audio_bytes)
            tmpfile.seek(0)
            captions = whisper_proxy.generate_captions(tmpfile.name, language=language)
            if enhance_captions:
                captions = await self._llm_service.enhance_captions(
                    captions, History(title="", content="", gender="male"), language
                )
            return captions
