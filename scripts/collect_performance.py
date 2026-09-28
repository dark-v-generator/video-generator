"""Collect the TikTok and Reddit numbers of the published videos.

Reads the TikTok Studio with the server's session, so it runs on the server
(``just prod-collect-performance``), never while a publish is running: both
use the same Chromium profile.

Usage:
    uv run python scripts/collect_performance.py
    uv run python scripts/collect_performance.py --lookback-days 60

    # A video the collection could not match: say which record it is.
    uv run python scripts/collect_performance.py --assign 7412345678901234567 42
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from src.core.container import container


async def _send_to_stdout(text: str) -> None:
    print(text, flush=True)


async def _collect(lookback_days: int | None) -> None:
    await container.performance_collection(progress=_send_to_stdout).collect(
        lookback_days=lookback_days
    )


def _assign(tiktok_video_id: str, record_id: int) -> None:
    container.performance_collection(progress=_send_to_stdout).assign(
        tiktok_video_id, record_id
    )
    print(f"Registro {record_id} ↔ TikTok {tiktok_video_id}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect TikTok and Reddit numbers for the published videos.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="How many days of posts to read (default: from config).",
    )
    mode.add_argument(
        "--assign",
        nargs=2,
        metavar=("TIKTOK_ID", "RECORD_ID"),
        help="Attach a TikTok video to a history record by hand.",
    )
    args = parser.parse_args()

    try:
        if args.assign:
            tiktok_video_id, record_id = args.assign
            _assign(tiktok_video_id, int(record_id))
        else:
            asyncio.run(_collect(args.lookback_days))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
