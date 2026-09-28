"""What every Chromium that touches the TikTok account shares.

The publisher and the Studio reader open the same profile, so they must
look like the same browser to TikTok: same profile directory, same user
agent, same launch flags. Kept free of browser-use and patchright so
either side can import it cheaply.
"""

from pathlib import Path
from typing import List

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Launch flags borrowed from patchright's defaults that are universally
# safe and meaningfully reduce automation fingerprint surface.
STEALTH_BROWSER_ARGS: List[str] = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-site-isolation-trials",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-dev-shm-usage",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
]


def profile_dir(cookies_path: str) -> Path:
    """The Chromium profile that lives next to the session cookies file."""
    cookies = Path(cookies_path).expanduser().resolve()
    return cookies.parent / (cookies.stem + "_userdata")
