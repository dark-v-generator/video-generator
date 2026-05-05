"""Trigger the daily auto-publish pipeline from the command line.

Discovers top stories, generates videos, and schedules them on TikTok
using the same logic as the Telegram bot's daily cron — but prints
progress to stdout instead of sending Telegram messages.

Usage:
    uv run python scripts/daily_auto_publish.py
    uv run python scripts/daily_auto_publish.py --count 2
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from bots.satisfying_bot import run_daily_auto_publish


async def _send_to_stdout(text: str) -> None:
    print(text, flush=True)


async def _main(count: int | None) -> None:
    await run_daily_auto_publish(_send_to_stdout, publish_count=count)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the daily auto-publish pipeline (find → generate → schedule).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Override the number of videos to generate (default: from config).",
    )
    args = parser.parse_args()

    try:
        asyncio.run(_main(args.count))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except Exception as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
