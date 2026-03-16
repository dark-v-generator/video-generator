from typing import List
from pydantic import BaseModel, Field, model_validator


class StoryImage(BaseModel):
    start_time: float = Field(..., title="When this image appears (seconds)")
    description: str = Field(..., title="Human-readable description of the scene")
    prompt: str = Field(..., title="Image generation prompt")


class ImageStory(BaseModel):
    introduction_end_time: float = Field(
        ..., title="When the title narration ends and images unblur (seconds)"
    )
    call_to_action_start_time: float = Field(
        ..., title="When the call-to-action overlay starts (seconds)"
    )
    images: List[StoryImage] = Field(
        ..., title="Ordered list of images with their timing"
    )

    @model_validator(mode="after")
    def validate_timeline(self) -> "ImageStory":
        if self.introduction_end_time < 0:
            raise ValueError("introduction_end_time must be >= 0")

        if self.call_to_action_start_time <= self.introduction_end_time:
            raise ValueError(
                "call_to_action_start_time must be after introduction_end_time"
            )

        if not self.images:
            raise ValueError("images list must not be empty")

        if self.images[0].start_time != 0:
            raise ValueError("first image must start at time 0")

        for i in range(1, len(self.images)):
            if self.images[i].start_time <= self.images[i - 1].start_time:
                raise ValueError(
                    f"image {i} start_time ({self.images[i].start_time}) "
                    f"must be after image {i - 1} start_time ({self.images[i - 1].start_time})"
                )

        if self.images[-1].start_time >= self.call_to_action_start_time:
            raise ValueError(
                "last image start_time must be before call_to_action_start_time"
            )

        return self
