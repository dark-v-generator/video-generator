from typing import List
from pydantic import BaseModel, Field
import yaml


class CaptionSegment(BaseModel):
    start: float = Field(0)
    end: float = Field(0)
    text: str = Field("")


class Captions(BaseModel):
    segments: List[CaptionSegment] = Field([])

    def with_speed(self, rate: float) -> "Captions":
        new_segments = [
            CaptionSegment(
                start=segment.start / rate,
                end=segment.end / rate,
                text=segment.text
            )
            for segment in self.segments
        ]
        return Captions(segments=new_segments)