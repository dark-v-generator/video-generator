from typing import List
from pytubefix import YouTube, Channel, Playlist
from src.proxies.interfaces import IYouTubeProxy
from src.entities.configs.proxies.youtube import PyTubeYouTubeConfig
import logging
import tempfile
import asyncio

logger = logging.getLogger(__name__)


class PyTubeProxy(IYouTubeProxy):
    def __init__(self, config: PyTubeYouTubeConfig):
        self.config = config

    async def list_video_ids(self, url: str) -> List[str]:
        """List video IDs from a YouTube channel or playlist URL"""
        return await asyncio.to_thread(self._extract_video_ids, url)

    def _extract_video_ids(self, url: str) -> List[str]:
        video_ids = []
        try:
            if "playlist" in url or "list=" in url:
                playlist = Playlist(url)
                video_ids = [vid for vid in playlist.video_urls]
            elif (
                "channel/" in url
                or "c/" in url
                or "user/" in url
                or url.startswith("https://www.youtube.com/@")
            ):
                channel = Channel(url)
                video_ids = [vid for vid in channel.video_urls]
            else:
                # Assume it's a single video url
                yt = YouTube(url)
                video_ids = [yt.watch_url]
        except Exception as e:
            logger.error(f"Failed to list video IDs for {url}: {e}")
            raise e

        # Extract just the IDs from the complete watch URLs to be safe
        extracted_ids = []
        for v_url in video_ids:
            try:
                if hasattr(v_url, "video_id"):
                    extracted_ids.append(v_url.video_id)
                elif isinstance(v_url, str):
                    yt = YouTube(v_url)
                    extracted_ids.append(yt.video_id)
            except Exception:
                # Fallback extraction if pytube fails
                if isinstance(v_url, str) and "v=" in v_url:
                    extracted_ids.append(v_url.split("v=")[1].split("&")[0])

        return list(set(extracted_ids))

    async def download_video(self, video_id: str, low_quality: bool = False) -> bytes:
        """Download a YouTube video and return its bytes"""
        return await asyncio.to_thread(self._download_video_sync, video_id, low_quality)

    def _download_video_sync(self, video_id: str, low_quality: bool = False) -> bytes:
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            yt = YouTube(url)

            # Get progressive streams
            streams = yt.streams.filter(
                progressive=True, file_extension="mp4"
            ).order_by("resolution")
            stream = streams.first() if low_quality else streams.desc().first()
            if not stream:
                # fallback to any mp4 stream
                fallback_streams = yt.streams.filter(file_extension="mp4").order_by(
                    "resolution"
                )
                stream = (
                    fallback_streams.first()
                    if low_quality
                    else fallback_streams.desc().first()
                )
                if not stream:
                    raise ValueError(
                        f"No suitable mp4 stream found for video_id {video_id}"
                    )

            with tempfile.TemporaryDirectory() as temp_dir:
                file_path = stream.download(output_path=temp_dir)
                with open(file_path, "rb") as f:
                    return f.read()

        except Exception as e:
            logger.error(f"Failed to download video {video_id}: {e}")
            raise e
