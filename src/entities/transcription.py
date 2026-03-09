from typing import List, Optional
from pydantic import BaseModel


class TranscriptionWord(BaseModel):
    word: str
    start: float
    end: float
    probability: Optional[float] = None


class TranscriptionResult(BaseModel):
    text: str
    words: List[TranscriptionWord]
    language: Optional[str] = None
