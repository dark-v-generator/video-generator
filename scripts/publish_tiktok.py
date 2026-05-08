"""Publish — or schedule — a video on TikTok via an AI-driven browser agent.

The script reads credentials from environment variables (or the project
``.env`` file): ``TIKTOK_EMAIL``, ``TIKTOK_PASSWORD``, and
``OPENROUTER_API_KEY``. The agent's underlying model is configurable
via ``TIKTOK_AGENT_MODEL`` (default: ``deepseek/deepseek-v4-flash``).

Cookies are persisted to ``.storage/tiktok_cookies.json`` between runs
so the agent only needs to log in once.

Usage:
    # Publish now
    uv run python scripts/publish_tiktok.py path/to/video.mp4 \
        --description "My caption" --hashtag fyp

    # Schedule for tomorrow at 18:00 (local time)
    uv run python scripts/publish_tiktok.py path/to/video.mp4 \
        --description "My caption" \
        --schedule-at "2026-05-05T18:00"

    # Schedule for "+6 hours from now"
    uv run python scripts/publish_tiktok.py path/to/video.mp4 \
        --schedule-in 6h
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from datetime import datetime, timedelta
from typing import Optional

from src.core.logging_config import get_logger
from src.core.secrets import secrets
from src.entities.config import MainConfig
from src.proxies.tiktok_publisher_proxy import BrowserUseTikTokPublisherProxy


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish a local video to TikTok using an AI agent."
    )
    parser.add_argument("video_path", type=str, help="Path to the .mp4 video file")
    parser.add_argument(
        "--description",
        type=str,
        default="",
        help="Caption / description for the post (will be typed verbatim)",
    )
    parser.add_argument(
        "--hashtag",
        action="append",
        default=[],
        dest="hashtags",
        help="Hashtag to append to the description. Can be repeated.",
    )
    parser.add_argument(
        "--cookies-path",
        type=str,
        default=None,
        help=(
            "Override config.yaml's tiktok_publisher_config.cookies_path."
            " Defaults to .storage/tiktok_cookies.json."
        ),
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=None,
        help=(
            "Force headless. Default: read from config.yaml"
            " (tiktok_publisher_config.headless)."
        ),
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=None,
        help=(
            "Override config.yaml's tiktok_publisher_config.max_steps"
            " (default 60)."
        ),
    )
    parser.add_argument(
        "--use-vision",
        action="store_true",
        default=None,
        help=(
            "Force screenshots-to-LLM on. Default: read from config.yaml"
            " (tiktok_publisher_config.use_vision). Required if you switch"
            " to a vision-capable model to solve image captchas."
        ),
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help=(
            "Override config.yaml's tiktok_publisher_config.agent_model"
            " (default deepseek/deepseek-v4-flash)."
        ),
    )
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config.yaml (default: $CONFIG_PATH or ./config.yaml)",
    )
    schedule_group = parser.add_mutually_exclusive_group()
    schedule_group.add_argument(
        "--schedule-at",
        type=_parse_iso_datetime,
        default=None,
        metavar="ISO_DATETIME",
        help=(
            "Schedule the post for an absolute local time, ISO-8601 format"
            " (e.g. 2026-05-05T18:00 or '2026-05-05 18:00'). TikTok allows"
            " up to 10 days in advance and at least ~20 minutes from now."
        ),
    )
    schedule_group.add_argument(
        "--schedule-in",
        type=_parse_relative_duration,
        default=None,
        metavar="DURATION",
        help=(
            "Schedule the post relative to now using a duration like 30m,"
            " 6h, 2d, or 1d12h. Resolved at run time and forwarded as"
            " --schedule-at."
        ),
    )
    return parser


_DURATION_RE = re.compile(
    r"(?P<days>\d+)\s*d|"
    r"(?P<hours>\d+)\s*h|"
    r"(?P<minutes>\d+)\s*m"
)


def _parse_iso_datetime(value: str) -> datetime:
    """argparse type for --schedule-at. Returns a naive local datetime.

    Accepts both 'YYYY-MM-DDTHH:MM' (with T) and 'YYYY-MM-DD HH:MM'
    (with space). Trailing seconds are accepted but optional.
    """
    candidate = value.strip().replace(" ", "T")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid ISO-8601 datetime '{value}'. "
            "Use e.g. 2026-05-05T18:00 or '2026-05-05 18:00'."
        ) from exc


def _parse_relative_duration(value: str) -> datetime:
    """argparse type for --schedule-in. Returns now + duration."""
    total = timedelta()
    matched = False
    for match in _DURATION_RE.finditer(value):
        matched = True
        if match.group("days"):
            total += timedelta(days=int(match.group("days")))
        elif match.group("hours"):
            total += timedelta(hours=int(match.group("hours")))
        elif match.group("minutes"):
            total += timedelta(minutes=int(match.group("minutes")))
    if not matched or total == timedelta():
        raise argparse.ArgumentTypeError(
            f"Invalid duration '{value}'. Use combinations of d/h/m, "
            "e.g. 30m, 6h, 2d, or 1d12h."
        )
    return datetime.now() + total


def _resolve_schedule_at(args: argparse.Namespace) -> Optional[datetime]:
    return args.schedule_at or args.schedule_in


async def _run(args: argparse.Namespace) -> int:
    logger = get_logger("publish_tiktok")

    if not secrets.openrouter_api_key:
        logger.error("OPENROUTER_API_KEY must be set (in .env or env).")
        return 2

    config_path = args.config or os.environ.get("CONFIG_PATH", "config.yaml")
    main_config = MainConfig.from_yaml(config_path)
    publisher_cfg = main_config.proxies.tiktok_publisher_config

    # CLI flags win over config; config wins over hard-coded defaults.
    model = args.model or publisher_cfg.agent_model
    cookies_path = args.cookies_path or publisher_cfg.cookies_path
    headless = (
        args.headless if args.headless is not None else publisher_cfg.headless
    )
    use_vision = (
        args.use_vision
        if args.use_vision is not None
        else publisher_cfg.use_vision
    )
    max_steps = (
        args.max_steps if args.max_steps is not None else publisher_cfg.max_steps
    )

    proxy = BrowserUseTikTokPublisherProxy(
        openrouter_api_key=secrets.openrouter_api_key,
        model=model,
        cookies_path=cookies_path,
        headless=headless,
        max_steps=max_steps,
        use_vision=use_vision,
    )

    schedule_at = _resolve_schedule_at(args)

    if schedule_at is not None:
        logger.info(
            "Scheduling %s on TikTok for %s using model=%s "
            "(cookies=%s, headless=%s)",
            args.video_path,
            schedule_at.strftime("%Y-%m-%d %H:%M"),
            model,
            cookies_path,
            headless,
        )
    else:
        logger.info(
            "Publishing %s to TikTok using model=%s (cookies=%s, headless=%s)",
            args.video_path,
            model,
            cookies_path,
            headless,
        )

    try:
        url = await proxy.publish_video(
            video_path=args.video_path,
            description=args.description,
            hashtags=args.hashtags,
            schedule_at=schedule_at,
        )
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1
    except ValueError as exc:
        logger.error("%s", exc)
        return 2
    except Exception:
        logger.exception("Failed to publish video to TikTok")
        return 1

    verb = "Scheduled" if schedule_at is not None else "Published"
    if url:
        logger.info("%s! URL: %s", verb, url)
        print(url)
    else:
        logger.warning(
            "Agent finished without returning a URL. Inspect the browser"
            " window or the logged history for details."
        )
    return 0


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
