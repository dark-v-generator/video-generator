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


def _patched_set_schedule(page, schedule):
    """
    Replaces the library's _set_schedule_video to work with TikTok's current UI
    which uses radio buttons + TUXTextInput dropdowns instead of the old switch +
    calendar/timepicker approach.
    """
    import pytz

    logger.debug("Setting schedule (patched)")

    tz_str = page.evaluate("Intl.DateTimeFormat().resolvedOptions().timeZone")
    local_schedule = schedule.astimezone(pytz.timezone(tz_str))

    container = page.locator('[data-e2e="schedule_container"]')
    container.locator('input[name="postSchedule"][value="schedule"]').locator("xpath=..").click()
    time.sleep(1)
    logger.info("Clicked Schedule radio button")

    # -- Time picker --
    picker = container.locator('.tiktok-timepicker-time-picker-container')
    time_input = container.locator('.TUXTextInputCore-input[readonly]').first

    if not picker.is_visible():
        time_input.click(force=True)
        time.sleep(0.5)

    picker.wait_for(state="visible", timeout=5000)

    hours = container.locator('span.tiktok-timepicker-left')
    minutes = container.locator('span.tiktok-timepicker-right')

    target_hour = hours.nth(local_schedule.hour)
    target_hour.scroll_into_view_if_needed()
    time.sleep(0.3)
    target_hour.click()

    minute_idx = local_schedule.minute // 5
    target_minute = minutes.nth(minute_idx)
    target_minute.scroll_into_view_if_needed()
    time.sleep(0.3)
    target_minute.click()

    page.mouse.click(0, 0)
    time.sleep(0.5)
    logger.info("Set time to %02d:%02d", local_schedule.hour, (minute_idx * 5))

    # -- Date picker --
    date_input = container.locator('.TUXTextInputCore-input[readonly]').nth(1)
    target_date_str = local_schedule.strftime("%Y-%m-%d")

    current_date = date_input.input_value()
    if current_date != target_date_str:
        date_input.click(force=True)
        time.sleep(0.5)
        target_day = str(local_schedule.day)
        day_cell = page.locator(
            f'.calendar-wrapper span.day.valid:text-is("{target_day}")'
        )
        if day_cell.count() == 0:
            page.locator('.calendar-wrapper span.arrow').last.click()
            time.sleep(0.5)
            day_cell = page.locator(
                f'.calendar-wrapper span.day.valid:text-is("{target_day}")'
            )
        day_cell.first.click()
        time.sleep(0.5)

    logger.info("Set date to %s", target_date_str)


_tiktok_upload._set_schedule_video = _patched_set_schedule


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
