from typing import Optional
from ..adapters.proxies.interfaces import ITranscriptionProxy, ILLMProxy

from .interfaces import ICaptionsService
from ..adapters.repositories.interfaces import IFileStorage
from ..entities.captions import Captions, CaptionSegment
from ..entities.language import Language
from ..core.logging_config import get_logger

class CaptionsService(ICaptionsService):
    """Captions generation service implementation"""

    def __init__(
        self,
        file_storage: IFileStorage,
        llm_proxy: ILLMProxy,
        transcription_proxy: ITranscriptionProxy,
    ):
        self._file_storage = file_storage
        self._llm_proxy = llm_proxy
        self._transcription_proxy = transcription_proxy
        self._logger = get_logger(__name__)

    async def generate_captions(
        self,
        audio_bytes: bytes,
        enhance_captions: bool = False,
        language: Optional[Language] = None,
        base_text: Optional[str] = None,
    ) -> Captions:
        """Generate captions from audio bytes; optionally enhance via LLM"""
        # Directly generate the TranscriptionResult from bytes
        transcription_result = self._transcription_proxy.transcribe(
            audio_bytes, language=language
        )

        caption_segments = [
            CaptionSegment(start=w.start, end=w.end, text=w.word)
            for w in transcription_result.words
        ]
        
        if enhance_captions:
            if not base_text:
                raise ValueError("base_text must be provided when enhance_captions is True")
                
            raw_transcription = [
                {"word": s.text, "start": s.start, "end": s.end, "probability": 1.0}
                for s in caption_segments
            ]
            
            enhanced = await self._llm_proxy.enhance_transcription(
                base_text=base_text,
                raw_transcription=raw_transcription
            )
            
            caption_segments = [
                CaptionSegment(start=e.get("start", 0), end=e.get("end", 0), text=e.get("word", ""))
                for e in enhanced
            ]

        captions = Captions(segments=caption_segments)
        return captions
