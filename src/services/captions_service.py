from dataclasses import dataclass
from typing import Optional
from ..proxies.interfaces import ITranscriptionProxy, ILLMProxy

from ..entities.captions import Captions, CaptionSegment
from ..entities.configs.services.captions import CaptionsConfig
from ..entities.editor.captions_clip import CaptionsClip
from ..entities.language import Language
from ..core.logging_config import get_logger


@dataclass
class CaptionsResult:
    clip: CaptionsClip
    captions: Captions


class CaptionsService:
    """Captions generation service that returns a CaptionsResult"""

    def __init__(
        self,
        llm_proxy: ILLMProxy,
        transcription_proxy: ITranscriptionProxy,
        captions_config: CaptionsConfig,
    ):
        self._llm_proxy = llm_proxy
        self._transcription_proxy = transcription_proxy
        self._captions_config = captions_config
        with open(self._captions_config.font_path, "rb") as f:
            self._font_bytes = f.read()
        self._logger = get_logger(__name__)

    async def generate_captions(
        self,
        audio_bytes: bytes,
        enhance_captions: bool = False,
        language: Optional[Language] = None,
        base_text: Optional[str] = None,
    ) -> CaptionsResult:
        """Generate captions from audio bytes and return a CaptionsResult"""
        transcription_result = self._transcription_proxy.transcribe(
            audio_bytes, language=language
        )

        caption_segments = [
            CaptionSegment(start=w.start, end=w.end, text=w.word)
            for w in transcription_result.words
        ]

        if enhance_captions:
            if not base_text:
                raise ValueError(
                    "base_text must be provided when enhance_captions is True"
                )

            raw_transcription = [
                {"word": s.text, "start": s.start, "end": s.end, "probability": 1.0}
                for s in caption_segments
            ]

            try:
                enhanced = await self._llm_proxy.enhance_transcription(
                    base_text=base_text, raw_transcription=raw_transcription
                )

                caption_segments_enhanced = []
                is_valid = isinstance(enhanced, list)

                if is_valid:
                    for e in enhanced:
                        if isinstance(e, dict):
                            caption_segments_enhanced.append(
                                CaptionSegment(
                                    start=e.get("start", 0),
                                    end=e.get("end", 0),
                                    text=e.get("word", ""),
                                )
                            )
                        else:
                            is_valid = False
                            break

                if is_valid and caption_segments_enhanced:
                    caption_segments = caption_segments_enhanced
                else:
                    self._logger.warning(
                        f"Invalid dict format returned by LLM enhancer. Falling back to raw transcription. Payload: {enhanced}"
                    )
            except Exception as e:
                self._logger.warning(
                    f"LLM enhancement failed with error: {e}. Falling back to raw transcription."
                )

        captions = Captions(segments=caption_segments)
        clip = CaptionsClip(
            captions=captions,
            config=self._captions_config,
            font_bytes=self._font_bytes,
        )
        return CaptionsResult(clip=clip, captions=captions)
