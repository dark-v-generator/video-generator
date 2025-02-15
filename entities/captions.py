from typing import List
from pydantic import BaseModel, Field
from entities.base_yaml_model import BaseYAMLModel


class CaptionSegment(BaseModel):
    start: float = Field(0)
    end: float = Field(0)
    text: str = Field("")
    probability: float = Field(1)


class Captions(BaseYAMLModel):
    segments: List[CaptionSegment] = Field([])

    def with_speed(self, rate: float) -> "Captions":
        new_segments = [
            CaptionSegment(
                start=segment.start / rate,
                end=segment.end / rate,
                text=segment.text,
                probability=segment.probability,
            )
            for segment in self.segments
        ]
        return Captions(segments=new_segments)
