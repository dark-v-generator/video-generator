"""Group the rows of a tuning data pack and print each group's evidence.

The pack (``just tuning-data --json``) already holds each video's relative
performance; a finding is a group of those videos. This prints, per group,
how many settled videos it has, their median relative, how many did 1.5x or
better and 0.8x or worse, and their record ids, so every number in a finding
comes from here and not from reading the rows by eye.

Only settled videos with a relative count: the rest are too recent, or had too
few neighbours, to say anything.

Usage:
    uv run python .claude/skills/prompt-tuning/scripts/group.py PACK --by kind
    uv run python .claude/skills/prompt-tuning/scripts/group.py PACK --by kind --by narrator_acts
    uv run python .claude/skills/prompt-tuning/scripts/group.py PACK --ids 322,330,341
    uv run python .claude/skills/prompt-tuning/scripts/group.py PACK --by goal --published-after 2026-09-23

Fields for --by: the label's kind, narrator_acts and title_promise; goal
(empty counts as base); title_length (under 90, 90-120, over 120 characters);
weekday (of published_at); watch (average watch under 25 s, 25-35 s, 35 s or
more).
"""

import argparse
import json
import statistics
import sys
from datetime import datetime

WEEKDAYS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _title_length(row: dict) -> str:
    n = len(row["title"] or "")
    return "<90" if n < 90 else "90-120" if n <= 120 else ">120"


def _weekday(row: dict) -> str | None:
    if not row["published_at"]:
        return None
    return WEEKDAYS[datetime.fromisoformat(row["published_at"]).weekday()]


def _watch(row: dict) -> str | None:
    seconds = row["avg_watch_seconds"]
    if seconds is None:
        return None
    return "<25s" if seconds < 25 else "25-35s" if seconds < 35 else ">=35s"


def _label(field: str):
    return lambda row: (row["label"] or {}).get(field)


FIELDS = {
    "kind": _label("kind"),
    "narrator_acts": _label("narrator_acts"),
    "title_promise": _label("title_promise"),
    "goal": lambda row: row["goal"] or "base",
    "title_length": _title_length,
    "weekday": _weekday,
    "watch": _watch,
}


def _evidence(rows: list[dict]) -> dict:
    relatives = [r["relative"] for r in rows]
    return {
        "videos": len(rows),
        "median_relative": round(statistics.median(relatives), 2) if rows else None,
        "at_least_1_5": sum(1 for v in relatives if v >= 1.5),
        "at_most_0_8": sum(1 for v in relatives if v <= 0.8),
        "is_lead": len(rows) < 10,
        "ids": sorted(r["record_id"] for r in rows),
    }


def _usable(pack: dict) -> list[dict]:
    return [r for r in pack["rows"] if r["settled"] and r["relative"] is not None]


def group(pack: dict, fields: list[str]) -> list[dict]:
    groups: dict[tuple, list[dict]] = {}
    for row in _usable(pack):
        key = tuple(FIELDS[f](row) for f in fields)
        groups.setdefault(key, []).append(row)
    return [
        {"group": dict(zip(fields, key)), **_evidence(rows)}
        for key, rows in sorted(
            groups.items(), key=lambda item: (-len(item[1]), str(item[0]))
        )
    ]


def by_ids(pack: dict, ids: list[int]) -> dict:
    usable = {r["record_id"]: r for r in _usable(pack)}
    known = {r["record_id"] for r in pack["rows"]}
    return {
        **_evidence([usable[i] for i in ids if i in usable]),
        "left_out": sorted(i for i in ids if i not in usable and i in known),
        "not_in_pack": sorted(i for i in ids if i not in known),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("pack", help="the JSON written by just tuning-data --json")
    parser.add_argument("--by", action="append", choices=sorted(FIELDS), default=[])
    parser.add_argument("--ids", help="comma-separated record ids to take together")
    parser.add_argument(
        "--published-after",
        type=datetime.fromisoformat,
        help="only videos published after this date: the ones new since a report",
    )
    args = parser.parse_args()
    if bool(args.by) == bool(args.ids):
        parser.error("give --by or --ids, not both")

    with open(args.pack, encoding="utf-8") as f:
        pack = json.load(f)
    if args.published_after:
        pack["rows"] = [
            r
            for r in pack["rows"]
            if r["published_at"]
            and datetime.fromisoformat(r["published_at"]) > args.published_after
        ]
    if args.ids:
        result = by_ids(pack, [int(i) for i in args.ids.split(",") if i.strip()])
    else:
        result = group(pack, args.by)
    # One group per line: the list is read side by side.
    for item in result if isinstance(result, list) else [result]:
        print(json.dumps(item, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
