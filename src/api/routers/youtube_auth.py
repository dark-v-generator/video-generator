import datetime
import threading
import time
from fastapi import APIRouter
from typing import Optional

from pydantic import BaseModel
from pytubefix import YouTube
from ...core.logging_config import get_logger

router = APIRouter(prefix="/api/youtube", tags=["youtube"])
logger = get_logger(__name__)


class YoutubeAuthResponse(BaseModel):
    verification_url: Optional[str] = None
    user_code: Optional[str] = None
    message: str = ""
    verified: bool = False


LOCK = threading.Lock()
AUTH_STARTED = threading.Event()
AUTH_COMPLETED = threading.Event()


def wait_for_youtube_auth_started(
    timeout: datetime.timedelta = datetime.timedelta(seconds=30),
    interval: datetime.timedelta = datetime.timedelta(milliseconds=100),
):
    start_time = datetime.datetime.now()
    while datetime.datetime.now() - start_time < timeout:
        if AUTH_STARTED.is_set():
            return True
        time.sleep(interval.total_seconds())
    return False


def wait_for_youtube_auth_completed(
    timeout: datetime.timedelta = datetime.timedelta(seconds=30),
    interval: datetime.timedelta = datetime.timedelta(milliseconds=100),
):
    start_time = datetime.datetime.now()
    while datetime.datetime.now() - start_time < timeout:
        if AUTH_COMPLETED.is_set():
            return True
        time.sleep(interval.total_seconds())
    return False


@router.post("/auth/initiate")
async def initiate_youtube_auth(
    timeout: int = 120,
) -> YoutubeAuthResponse:
    """Initiate YouTube OAuth flow and return verification URL and code"""
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    response = YoutubeAuthResponse()

    with LOCK:
        AUTH_STARTED.clear()
        AUTH_COMPLETED.clear()

    def custom_oauth_verifier(verification_url: str, user_code: str):
        logger.info(f"OAuth initiated - URL: {verification_url}, Code: {user_code}")
        with LOCK:
            AUTH_STARTED.set()
            response.verification_url = verification_url
            response.user_code = user_code
            response.verified = False
            response.message = (
                f"Please visit {verification_url} and enter code: {user_code}"
            )
            logger.info("YouTube auth started")
        wait_for_youtube_auth_completed(
            timeout=datetime.timedelta(seconds=timeout),
        )

    def try_access_video_thread():
        video_title = YouTube(
            video_url,
            "WEB_CREATOR",
            use_oauth=True,
            oauth_verifier=custom_oauth_verifier,
        ).title
        logger.info(f"Authentication completed successfully! Accessed: {video_title}")
        with LOCK:
            AUTH_STARTED.set()
            AUTH_COMPLETED.set()
            response.verified = True
            response.message = (
                f"Authentication completed successfully! Accessed: {video_title}"
            )

    thread = threading.Thread(target=try_access_video_thread)
    thread.start()
    wait_for_youtube_auth_started(
        timeout=datetime.timedelta(seconds=5),
    )

    return response


@router.post("/auth/complete")
async def complete_youtube_auth(
    timeout: int = 10,
):
    """Complete YouTube OAuth flow by testing access to a restricted video"""
    complete_youtube_auth()
    wait_for_youtube_auth_completed(
        timeout=datetime.timedelta(seconds=timeout),
    )
    try:
        video_title = YouTube(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "WEB_CREATOR",
            use_oauth=True,
        ).title

        return YoutubeAuthResponse(
            verified=True,
            message=f"Authentication completed successfully! Accessed: {video_title}",
        )
    except Exception as e:
        return YoutubeAuthResponse(
            verified=False,
            message=f"Authentication failed: {e}",
        )
