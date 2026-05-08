"""Trigger the daily auto-publish pipeline from the command line.

Supports three modes:
  - Full pipeline (default): discover stories, generate videos, then publish.
  - Generate only (--generate-only): discover + generate, skip publishing.
  - Publish only (--publish-only DIR): schedule pre-generated videos from DIR.

Usage:
    # Full pipeline
    uv run python scripts/daily_auto_publish.py
    uv run python scripts/daily_auto_publish.py --count 2

    # Generate only (saves videos + manifests to output/daily/)
    uv run python scripts/daily_auto_publish.py --generate-only
    uv run python scripts/daily_auto_publish.py --generate-only --output-dir output/batch1

    # Publish only (reads from a previous generate run)
    uv run python scripts/daily_auto_publish.py --publish-only output/daily
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from bots.satisfying_bot import (
    load_generated_videos,
    run_daily_auto_publish,
    run_daily_generate,
    run_daily_publish,
)


async def _send_to_stdout(text: str) -> None:
    print(text, flush=True)


async def _run_full(count: int | None, output_dir: str) -> None:
    await run_daily_auto_publish(
        _send_to_stdout, publish_count=count, output_dir=output_dir,
    )


async def _run_generate(count: int | None, output_dir: str) -> None:
    await run_daily_generate(
        _send_to_stdout, publish_count=count, output_dir=output_dir,
    )


async def _run_publish(directory: str) -> None:
    videos = load_generated_videos(directory)
    if not videos:
        print(f"No generated videos found in {directory}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Found {len(videos)} videos in {directory}")
    await run_daily_publish(_send_to_stdout, videos)


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
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output/daily",
        help="Directory for generated videos (default: output/daily).",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--generate-only",
        action="store_true",
        help="Only discover stories and generate videos; skip publishing.",
    )
    mode.add_argument(
        "--publish-only",
        type=str,
        metavar="DIR",
        help="Only publish pre-generated videos from DIR (skip discovery + generation).",
    )

    args = parser.parse_args()

    try:
        if args.publish_only:
            asyncio.run(_run_publish(args.publish_only))
        elif args.generate_only:
            asyncio.run(_run_generate(args.count, args.output_dir))
        else:
            asyncio.run(_run_full(args.count, args.output_dir))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 130
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 1
    except Exception as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
