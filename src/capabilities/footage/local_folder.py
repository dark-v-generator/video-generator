import logging
import random
from pathlib import Path

from ...entities.configs.services.video import VideoConfig
from ...entities.editor import video_clip
from .contract import Footage, FootageShortfallError

logger = logging.getLogger(__name__)


class LocalFolderFootageSource:
    """Background footage from the ``.mp4`` files of one directory; no network."""

    def __init__(self, directory: str, video_config: VideoConfig):
        self._directory = Path(directory)
        if not self._directory.is_dir():
            raise ValueError(f"local_footage_dir is not a directory: {directory}")
        self._video_config = video_config

    async def compile(
        self, *, min_duration: float, low_quality: bool = False
    ) -> Footage:
        # low_quality only picks the download resolution for YouTube; local
        # files are what they are and the composer resizes them.
        paths = sorted(
            path
            for path in self._directory.iterdir()
            if path.is_file() and path.suffix.lower() == ".mp4"
        )
        random.shuffle(paths)

        video = video_clip.VideoClip()
        sources: list[str] = []
        total_duration = 0.0

        for path in paths:
            new_video = video_clip.VideoClip(file_path=str(path))
            duration = float(new_video.clip.duration or 0)
            if duration <= 0:
                raise ValueError(f"Background clip has no duration: {path}")

            sources.append(path.name)
            new_video.apply_anti_fingerprint(self._video_config.anti_fingerprint)
            video.concat(new_video)
            total_duration += duration

            if total_duration >= min_duration:
                logger.info(
                    "Compiled %.1fs of local footage from %d clip(s) in %s",
                    total_duration,
                    len(sources),
                    self._directory,
                )
                return Footage(clip=video, sources=sources)

        raise FootageShortfallError(
            min_duration,
            total_duration,
            f"{len(paths)} .mp4 file(s) in {self._directory}",
        )
