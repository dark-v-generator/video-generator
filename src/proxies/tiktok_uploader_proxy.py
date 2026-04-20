import datetime
import logging
from typing import Optional

from tiktok_uploader.upload import TikTokUploader

from src.entities.configs.proxies.tiktok import TikTokUploaderConfig
from src.proxies.interfaces import ITikTokProxy

logger = logging.getLogger(__name__)


class TikTokUploaderProxy(ITikTokProxy):
    def __init__(self, config: TikTokUploaderConfig):
        self._config = config

    def upload_video(
        self,
        video_path: str,
        description: str,
        schedule: Optional[datetime.datetime] = None,
    ) -> None:
        action = f"scheduled for {schedule} UTC" if schedule else "immediately"
        logger.info("Uploading video to TikTok %s: %s", action, video_path)

        uploader = TikTokUploader(
            cookies=self._config.cookies_path,
            headless=self._config.headless,
            browser=self._config.browser,
        )

        uploader.upload_video(
            video_path,
            description=description,
            schedule=schedule,
        )

        logger.info("TikTok upload complete")
