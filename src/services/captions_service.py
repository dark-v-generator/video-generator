import tempfile

from ..adapters.proxies.interfaces import ITranscriptionProxy

from ..services.llm.interfaces import ILLMService

from .interfaces import ICaptionsService
from ..adapters.repositories.interfaces import IFileStorage
from ..entities.captions import Captions, CaptionSegment
from ..entities.language import Language
from ..entities.history import History
from ..core.logging_config import get_logger


class CaptionsService(ICaptionsService):
    """Captions generation service implementation"""

    def __init__(
        self,
        file_storage: IFileStorage,
        llm_service: ILLMService,
        transcription_proxy: ITranscriptionProxy,
    ):
        self._file_storage = file_storage
        self._llm_service = llm_service
        self._transcription_proxy = transcription_proxy
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
        # Directly generate the TranscriptionResult from bytes
        transcription_result = self._transcription_proxy.transcribe(
            audio_bytes, language=language
        )

        caption_segments = [
            CaptionSegment(start=w.start, end=w.end, text=w.word)
            for w in transcription_result.words
        ]
        captions = Captions(segments=caption_segments)
        if enhance_captions:
            captions = await self._llm_service.enhance_captions(
                captions, History(title="", content="", gender="male"), language
            )
        return captions
