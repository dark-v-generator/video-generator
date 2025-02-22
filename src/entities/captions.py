from typing import List
from pydantic import BaseModel, Field
from src.entities.base_yaml_model import BaseYAMLModel


class CaptionSegment(BaseModel):
    start: float = Field(0)
    end: float = Field(0)
    text: str = Field("")


class Captions(BaseYAMLModel):
    segments: List[CaptionSegment] = Field([])

    def with_speed(self, rate: float) -> "Captions":
        new_segments = [
            CaptionSegment(
                start=segment.start / rate,
                end=segment.end / rate,
                text=segment.text,
            )
            for segment in self.segments
        ]
        return Captions(segments=new_segments)

    def stripped(self) -> "Captions":
        return Captions(
            segments=[
                CaptionSegment(
                    start=segment.start, end=segment.end, text=segment.text.strip()
                )
                for segment in self.segments
            ]
        )
