"""Bring what was published before the history existed into it.

Every row of the publish log becomes a publish attempt, under a minimal record
for its video (title, post, part and summary from the manifest when there is
one; no Reddit numbers and no grade, those are gone). Running it again adds
nothing: a row whose attempt is already recorded is counted and skipped.

A video is its path and its post: the daily run writes output/daily/story_NN.mp4
every day, so the path alone names a different story each day.

Usage:
    uv run python scripts/import_history.py
    uv run python scripts/import_history.py --csv .storage/tiktok_publish_log.csv \\
        --manifests output/daily
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.core.container import container
from src.entities.history import PublishAttempt, VideoRecord
from src.storage import HistoryStore

DEFAULT_CSV = ".storage/tiktok_publish_log.csv"
# The run logs the row, then records the attempt a moment later; the row's
# time is cut to the second.
SAME_ATTEMPT = timedelta(seconds=5)


@dataclass
class ImportResult:
    records: int = 0
    attempts: int = 0
    existing: int = 0

    def __str__(self) -> str:
        return (
            f"{self.records} registros criados, {self.attempts} tentativas, "
            f"{self.existing} já existiam"
        )


def _local(text: str) -> Optional[datetime]:
    """The log writes the server's local time without an offset."""
    return datetime.fromisoformat(text).astimezone() if text else None


def _manifests(directories: list[str]) -> dict[tuple[str, str], dict]:
    """Each manifest by the video it describes, whether or not the mp4 is left."""
    found = {}
    for directory in directories:
        for path in sorted(Path(directory).glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            found[(data["video_path"], data.get("post_url", ""))] = data
    return found


def _record_id(
    history: HistoryStore,
    row: dict,
    manifests: dict[tuple[str, str], dict],
    result: ImportResult,
) -> int:
    found = history.find_record_by_video_path(
        row["video_path"], post_url=row["post_url"]
    )
    if found is not None:
        return found.id
    manifest = manifests.get((row["video_path"], row["post_url"]), {})
    part = manifest.get("part") or 1
    result.records += 1
    return history.add_video_record(
        VideoRecord(
            created_at=_local(row["created_at"]),
            run_id=None,
            video_path=row["video_path"],
            title=row["title"],
            summary=manifest.get("summary", ""),
            post_url=row["post_url"],
            # The manifest knows the part, not how many there were.
            part_index=part,
            part_count=part,
            imported=True,
        ),
        None,
    )


def import_publish_log(
    history: HistoryStore, csv_path: str, manifest_dirs: list[str]
) -> ImportResult:
    manifests = _manifests(manifest_dirs)
    result = ImportResult()
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    for row in rows:
        record_id = _record_id(history, row, manifests, result)
        attempted_at = _local(row["created_at"])
        if any(
            known.status == row["status"]
            and abs(known.attempted_at - attempted_at) <= SAME_ATTEMPT
            for known in history.publish_attempts(record_id)
        ):
            result.existing += 1
            continue
        history.add_publish_attempt(
            record_id,
            PublishAttempt(
                attempted_at=attempted_at,
                status=row["status"],
                scheduled_at=_local(row["scheduled_at"]),
                hashtags=[tag.lstrip("#") for tag in row["hashtags"].split()],
                publish_result=row["publish_result"],
                error=row["error"],
            ),
        )
        result.attempts += 1
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import the publish log and manifests into the history, once.",
    )
    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV,
        help=f"Publish log to import (default: {DEFAULT_CSV}).",
    )
    parser.add_argument(
        "--manifests",
        action="append",
        default=[],
        metavar="DIR",
        help="Directory of manifests for summaries and parts (repeatable).",
    )
    args = parser.parse_args(argv)

    try:
        result = import_publish_log(container.history_store(), args.csv, args.manifests)
    except Exception as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
