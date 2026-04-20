import datetime
import logging
import time
from typing import Optional

import tiktok_uploader.upload as _tiktok_upload
from tiktok_uploader.upload import TikTokUploader

from src.entities.configs.proxies.tiktok import TikTokUploaderConfig
from src.proxies.interfaces import ITikTokProxy

logger = logging.getLogger(__name__)

_JOYRIDE_CSS = """
#react-joyride-portal,
.react-joyride__overlay,
[data-test-id="overlay"] {
    display: none !important;
    pointer-events: none !important;
    opacity: 0 !important;
    z-index: -1 !important;
}
"""

_original_go_to_upload = _tiktok_upload._go_to_upload


def _patched_go_to_upload(page):
    _original_go_to_upload(page)
    try:
        page.add_style_tag(content=_JOYRIDE_CSS)
        time.sleep(1)
        logger.info("Injected CSS to suppress Joyride overlay")
    except Exception:
        pass


_tiktok_upload._go_to_upload = _patched_go_to_upload


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

        naive_schedule = schedule.replace(tzinfo=None) if schedule else None

        uploader = TikTokUploader(
            cookies=self._config.cookies_path,
            headless=self._config.headless,
            browser=self._config.browser,
        )

        success = uploader.upload_video(
            video_path,
            description=description,
            schedule=naive_schedule,
        )

        if not success:
            raise RuntimeError("TikTok upload failed — check logs for details")

        logger.info("TikTok upload complete")
