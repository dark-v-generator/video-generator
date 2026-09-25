"""What the daily run keeps between runs: manifests and the publish log."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional, Protocol

from ..entities.generated_video import GeneratedVideo


@dataclass
class PublishLogEntry:
    status: Literal["scheduled", "failed"]
    scheduled_at: Optional[datetime]
    video: GeneratedVideo
    hashtags: list[str]
    publish_result: str = ""
    error: str = ""


class RunStore(Protocol):
    def save_manifest(self, video: GeneratedVideo, output_dir: str) -> str: ...

    def load_manifests(self, output_dir: str) -> list[GeneratedVideo]: ...

    def append_publish_log(self, entry: PublishLogEntry) -> None: ...

    def scheduled_post_urls(self) -> set[str]: ...
