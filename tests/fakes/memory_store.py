"""A run store over dicts and lists: the contract a database store will meet."""

import dataclasses
import os
from typing import Dict, List

from src.entities.generated_video import GeneratedVideo
from src.storage import PublishLogEntry


class InMemoryRunStore:
    def __init__(self):
        # manifests[output_dir][basename of the video] -> the video
        self.manifests: Dict[str, Dict[str, GeneratedVideo]] = {}
        self.log: List[PublishLogEntry] = []

    def save_manifest(self, video: GeneratedVideo, output_dir: str) -> str:
        name = os.path.basename(video.video_path)
        self.manifests.setdefault(output_dir, {})[name] = dataclasses.replace(video)
        return name

    def load_manifests(self, output_dir: str) -> list[GeneratedVideo]:
        saved = self.manifests.get(output_dir, {})
        return [saved[name] for name in sorted(saved)]

    def append_publish_log(self, entry: PublishLogEntry) -> None:
        self.log.append(entry)

    def scheduled_post_urls(self) -> set[str]:
        return {
            entry.video.post_url
            for entry in self.log
            if entry.status == "scheduled" and entry.video.post_url
        }
