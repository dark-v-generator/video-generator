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


@router.post("/auth/initiate")
async def initiate_youtube_auth(
    timeout: int = 120,
) -> YoutubeAuthResponse:
    """Initiate YouTube OAuth flow and return verification URL and code"""
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    with LOCK:
        AUTH_STARTED.clear()
        AUTH_COMPLETED.clear()
    response = YoutubeAuthResponse()

    def custom_oauth_verifier(verification_url: str, user_code: str):
        logger.info(f"OAuth initiated - URL: {verification_url}, Code: {user_code}")
        with LOCK:
            response.verification_url = verification_url
            response.user_code = user_code
            response.verified = False
            response.message = (
                f"Please visit {verification_url} and enter code: {user_code}"
            )
            AUTH_STARTED.set()
        for _ in range(timeout):
            if AUTH_COMPLETED.is_set():
                logger.info("Auth complete set")
                break
            logger.info("Auth not set, waiting for 1 second")
            time.sleep(1)

    def try_access_video_thread():
        video_title = YouTube(
            video_url,
            "WEB_CREATOR",
            use_oauth=True,
            oauth_verifier=custom_oauth_verifier,
        ).title
        with LOCK:
            response.verified = True
            response.message = (
                f"Authentication completed successfully! Accessed: {video_title}"
            )
            AUTH_COMPLETED.set()
            return

    thread = threading.Thread(target=try_access_video_thread)
    thread.start()
    for _ in range(timeout):
        if AUTH_STARTED.is_set() or AUTH_COMPLETED.is_set():
            return response
        time.sleep(1)

    return YoutubeAuthResponse(
        verification_url=None,
        user_code=None,
        verified=False,
        message=f"Authentication failed: Timeout",
    )


@router.post("/auth/complete")
async def complete_youtube_auth():
    """Complete YouTube OAuth flow by testing access to a restricted video"""
    with LOCK:
        AUTH_COMPLETED.set()
    return {"message": "Auth complete set"}
