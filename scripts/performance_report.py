"""Print the crossed view of the history: one row per video with its grade,
its Reddit numbers at discovery and now, its recipe and its newest TikTok
numbers, so a high grade that flopped sits next to a low grade that took off.

Reads only the history file (``HISTORY_DB_PATH``, default
``.storage/history.sqlite``); on the laptop, pull the server's with
``just sync-history`` first. No proxy, key or browser is involved, and the
container is not imported: its model libraries alone take seconds to load.

Usage:
    uv run python scripts/performance_report.py --sort grade_overall:desc
    uv run python scripts/performance_report.py --sort latest_views \\
        --filter grade_verdict=Excelente --since 2026-09-01
    uv run python scripts/performance_report.py --csv /tmp/cross.csv
    uv run python scripts/performance_report.py --columns
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime
from typing import Callable, Optional

from src.core.paths import history_db_path
from src.entities.history import CrossedRow
from src.storage import CROSSED_COLUMNS, SqliteHistoryStore, UnknownColumnError

TITLE_WIDTH = 40


def _number(value: object) -> str:
    return "" if value is None else f"{value:.0f}"


def _percent(value: Optional[float]) -> str:
    return "" if value is None else f"{value * 100:.1f}%"


def _upvotes_now(columns: dict) -> str:
    if columns["latest_reddit_available"] is False:
        return "indisp."
    return _number(columns["latest_reddit_score"])


def _title(value: str) -> str:
    if len(value) <= TITLE_WIDTH:
        return value
    return value[: TITLE_WIDTH - 1] + "…"


# (header, value from the row's columns, right-aligned)
TABLE: list[tuple[str, Callable[[dict], str], bool]] = [
    ("id", lambda c: str(c["id"]), True),
    ("criado", lambda c: c["created_at"].astimezone().strftime("%Y-%m-%d"), False),
    ("título", lambda c: _title(c["title"]), False),
    ("nota", lambda c: _number(c["grade_overall"]), True),
    ("veredito", lambda c: c["grade_verdict"] or "", False),
    ("up desc.", lambda c: _number(c["discovery_score"]), True),
    ("up agora", _upvotes_now, True),
    ("views", lambda c: _number(c["latest_views"]), True),
    ("likes", lambda c: _number(c["latest_likes"]), True),
    ("coment.", lambda c: _number(c["latest_comments"]), True),
    ("shares", lambda c: _number(c["latest_shares"]), True),
    ("saves", lambda c: _number(c["latest_saves"]), True),
    (
        "watch",
        lambda c: (
            ""
            if c["latest_avg_watch_seconds"] is None
            else f"{c['latest_avg_watch_seconds']:.1f}s"
        ),
        True,
    ),
    ("% fim", lambda c: _percent(c["latest_full_watch_ratio"]), True),
    ("% 3s", lambda c: _percent(c["latest_retained_3s"]), True),
    ("% FYP", lambda c: _percent(c["latest_for_you_ratio"]), True),
    ("seguid.", lambda c: _number(c["latest_new_followers"]), True),
    ("prompt", lambda c: (c["story_prompt_version"] or "")[:8], False),
    ("modelo", lambda c: c["writer_model"] or "", False),
]


def render_table(rows: list[CrossedRow]) -> str:
    cells = [[value(row.columns()) for _, value, _ in TABLE] for row in rows]
    headers = [header for header, _, _ in TABLE]
    widths = [
        max(len(text) for text in column)
        for column in zip(headers, *cells, strict=True)
    ]

    def line(texts: list[str]) -> str:
        return "  ".join(
            text.rjust(width) if right else text.ljust(width)
            for text, width, (_, _, right) in zip(texts, widths, TABLE, strict=True)
        ).rstrip()

    return "\n".join([line(headers), *(line(texts) for texts in cells)])


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def write_csv(rows: list[CrossedRow], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CROSSED_COLUMNS)
        for row in rows:
            writer.writerow([_csv_value(v) for v in row.columns().values()])


def _sort(text: str) -> tuple[str, bool]:
    column, _, direction = text.partition(":")
    if direction not in ("", "asc", "desc"):
        raise argparse.ArgumentTypeError(f"direction must be asc or desc: {text}")
    return column, direction == "desc"


def _filter(text: str) -> tuple[str, str]:
    column, equals, value = text.partition("=")
    if not equals:
        raise argparse.ArgumentTypeError(f"expected COLUMN=VALUE: {text}")
    return column, value


def _since(text: str) -> datetime:
    """A date or datetime in local time, as the operator reads the table."""
    return datetime.fromisoformat(text).astimezone()


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the crossed view of the history, one row per video.",
    )
    parser.add_argument(
        "--since",
        type=_since,
        help="Only videos created on or after this date (YYYY-MM-DD, local).",
    )
    parser.add_argument(
        "--sort",
        type=_sort,
        metavar="COLUMN[:desc]",
        help="Sort by a column; empty values go last (default: by id).",
    )
    parser.add_argument(
        "--filter",
        type=_filter,
        action="append",
        default=[],
        metavar="COLUMN=VALUE",
        help="Keep rows whose column equals the value (repeatable).",
    )
    parser.add_argument(
        "--csv",
        metavar="FILE",
        help="Write the rows with every column to a CSV file instead of printing.",
    )
    parser.add_argument(
        "--columns",
        action="store_true",
        help="List the columns --sort, --filter and --csv know, and exit.",
    )
    args = parser.parse_args(argv)

    if args.columns:
        print("\n".join(CROSSED_COLUMNS))
        return 0
    try:
        rows = SqliteHistoryStore(history_db_path()).crossed_view(
            since=args.since, filters=dict(args.filter), sort=args.sort
        )
        if args.csv:
            write_csv(rows, args.csv)
            print(f"{len(rows)} vídeos gravados em {args.csv}")
        else:
            print(render_table(rows))
            print(f"\n{len(rows)} vídeos", flush=True)
    except BrokenPipeError:
        # Piped into head: the reader has what it wanted. Point stdout at
        # /dev/null so the exit flush does not raise again.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    except UnknownColumnError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Fatal: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
