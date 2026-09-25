"""The run store the server uses: JSON manifests next to the videos, a CSV log."""

import csv
import json
import logging
import os
from datetime import datetime

from ..entities.generated_video import GeneratedVideo
from .contract import PublishLogEntry

logger = logging.getLogger(__name__)

LOG_FIELDS = [
    "created_at",
    "status",
    "scheduled_at",
    "video_path",
    "title",
    "post_url",
    "hashtags",
    "publish_result",
    "error",
]


def _manifest_path(video_path: str, output_dir: str) -> str:
    base = os.path.splitext(os.path.basename(video_path))[0]
    return os.path.join(output_dir, f"{base}.json")


class FileRunStore:
    def __init__(self, publish_log_path: str):
        self._publish_log_path = publish_log_path

    def save_manifest(self, video: GeneratedVideo, output_dir: str) -> str:
        manifest = {
            "video_path": video.video_path,
            "title": video.title,
            "summary": video.summary,
            "post_url": video.post_url,
            "source": video.source,
        }
        if video.part is not None:
            manifest["part"] = video.part
        path = _manifest_path(video.video_path, output_dir)
        with open(path, "w") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
        return path

    def load_manifests(self, output_dir: str) -> list[GeneratedVideo]:
        """Every manifest in *output_dir* whose video is still there, by file name.

        Manifests written before ``source`` and ``part`` existed still load.
        """
        videos = []
        for name in sorted(os.listdir(output_dir)):
            if not name.endswith(".json"):
                continue
            with open(os.path.join(output_dir, name)) as f:
                data = json.load(f)
            mp4 = data["video_path"]
            if not os.path.isabs(mp4):
                mp4 = os.path.join(output_dir, os.path.basename(mp4))
            if not os.path.exists(mp4):
                logger.warning("Video file missing, skipping: %s", mp4)
                continue
            videos.append(
                GeneratedVideo(
                    video_path=mp4,
                    title=data["title"],
                    summary=data.get("summary", ""),
                    post_url=data.get("post_url", ""),
                    source=data.get("source", "auto"),
                    part=data.get("part"),
                )
            )
        return videos

    def append_publish_log(self, entry: PublishLogEntry) -> None:
        """Append one row; a log that cannot be written must not stop the run."""
        path = self._publish_log_path
        row = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": entry.status,
            "scheduled_at": (
                entry.scheduled_at.isoformat(timespec="minutes")
                if entry.scheduled_at
                else ""
            ),
            "video_path": entry.video.video_path,
            "title": entry.video.title,
            "post_url": entry.video.post_url,
            "hashtags": " ".join(f"#{tag}" for tag in entry.hashtags),
            "publish_result": entry.publish_result,
            "error": entry.error,
        }

        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            file_exists = os.path.exists(path)
            with open(path, "a", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
        except Exception:
            logger.exception("Failed to append TikTok publish log")

    def scheduled_post_urls(self) -> set[str]:
        """Posts already scheduled on TikTok, so discovery does not offer them again.

        Only ``scheduled`` rows count: a failed attempt left the story unpublished
        and it deserves another shot.
        """
        if not os.path.exists(self._publish_log_path):
            return set()

        with open(self._publish_log_path, newline="", encoding="utf-8") as f:
            return {
                row["post_url"]
                for row in csv.DictReader(f)
                if row.get("status") == "scheduled" and row.get("post_url")
            }
