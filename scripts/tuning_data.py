"""Print every number a tuning report needs, already worked out: each video's
views against its neighbours, whether it has settled, the channel's weeks,
the uploads lost, the open cycle against the previous one and each open
experiment's progress. The /prompt-tuning skill reads this and interprets;
it does not calculate.

Refuses, with exit code 2 and one line saying what to do, when the data
cannot support findings: the last collection is too old, or too few videos
of the period have settled.

Reads the history file (``HISTORY_DB_PATH``; on the laptop, pull the
server's with ``just sync-history`` first) and the tuning records
(``TUNING_DIR``). Like the crossed view, it does not import the container.

Usage:
    uv run python scripts/tuning_data.py
    uv run python scripts/tuning_data.py --since 2026-08-29 --until 2026-09-28
    uv run python scripts/tuning_data.py --days 45 --json /tmp/pack.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from src.capabilities.tuning import (
    Video,
    ambiguous_goals,
    compare_cycles,
    experiment_progress,
    lost_uploads,
    measure,
    prompt_drift,
    share_achieved,
    weekly_channel,
)
from src.core.paths import history_db_path, tuning_dir
from src.entities.tuning import PROMPT_FILES, StoryLabel
from src.prompts.loader import PROMPTS_DIR, fingerprints
from src.storage import (
    FileTuningRecords,
    HistoryStore,
    SqliteHistoryStore,
    TuningError,
    TuningRecords,
)

COLLECT = "rode `just prod-collect-performance`"


class Refusal(Exception):
    """The data cannot support findings; the message says what to do."""


def now() -> datetime:
    return datetime.now().astimezone()


def _local(value: Optional[datetime]) -> Optional[str]:
    """Local time without the offset, as the operator reads the table."""
    if value is None:
        return None
    return value.astimezone().replace(tzinfo=None).isoformat(timespec="seconds")


def _round(value: Optional[float], digits: int = 2) -> Optional[float]:
    return None if value is None else round(value, digits)


def _row(video: Video, label: Optional[StoryLabel]) -> dict:
    columns = video.row.columns()
    return {
        "record_id": video.record_id,
        "title": columns["title"],
        "summary": columns["summary"],
        "published_at": _local(video.published_at),
        "settled": video.settled,
        "views": video.views,
        "relative": _round(video.relative),
        "neighbours": video.neighbours,
        "grade_overall": columns["grade_overall"],
        "avg_watch_seconds": columns["latest_avg_watch_seconds"],
        "retained_3s": _round(columns["latest_retained_3s"], 3),
        "for_you_share": _round(columns["latest_for_you_ratio"], 3),
        "new_followers": columns["latest_new_followers"],
        "goal": video.goal,
        "exploration_experiment": columns["exploration_experiment"],
        "exploration_fit": columns["exploration_fit"],
        "cycle": video.cycle,
        "story_prompt_version": columns["story_prompt_version"],
        "grading_prompt_version": columns["grading_prompt_version"],
        "label": (
            {
                "kind": label.kind,
                "narrator_acts": label.narrator_acts,
                "title_promise": label.title_promise,
            }
            if label
            else None
        ),
    }


def build(
    history: HistoryStore,
    records: TuningRecords,
    *,
    since: date,
    until: date,
    min_settled: int,
    max_age_days: int,
    settle_days: int,
    at: datetime,
) -> dict:
    """The package for the period, or Refusal before anything is built."""
    collections = history.collections()
    if not collections:
        raise Refusal(f"nenhuma coleta no histórico; {COLLECT}")
    data_as_of = max(c.finished_at for c in collections)
    if at - data_as_of > timedelta(days=max_age_days):
        raise Refusal(f"última coleta em {data_as_of.astimezone():%Y-%m-%d}; {COLLECT}")

    # The whole history: a video's neighbours and its cycle's videos do not
    # stop at the period's edges.
    rows = history.crossed_view()
    attempts = {row.record.id: history.publish_attempts(row.record.id) for row in rows}
    videos = measure(rows, attempts, settle_days)
    in_period = [v for v in videos if since <= v.made_on <= until]
    considered = [v for v in in_period if v.settled]
    if len(considered) < min_settled:
        raise Refusal(
            f"{len(considered)} vídeos assentados no período; o mínimo é"
            f" {min_settled}; amplie com `--days`"
        )

    cycles = records.cycles()
    cycle = records.open_cycle()
    plan = records.exploration_plan()
    labels = records.story_labels()
    comparison = compare_cycles(videos, cycles)
    # Slots kept since the share was set; a share never set kept none to count.
    slots, filled = (
        history.slot_counts(plan.share_since) if plan.share_since else (None, None)
    )
    return {
        "generated_at": _local(at),
        "period": {"since": since.isoformat(), "until": until.isoformat()},
        "data_as_of": _local(data_as_of),
        "cycle": {
            "number": cycle.number,
            "opened": cycle.opened.isoformat(),
            "deployed": cycle.deployed.isoformat() if cycle.deployed else None,
            "prompts": cycle.prompts.model_dump(),
        },
        "prompt_drift": [
            asdict(d)
            for d in prompt_drift(cycle, fingerprints(PROMPT_FILES, PROMPTS_DIR))
        ],
        "videos": {
            "considered": len(considered),
            "excluded": {
                "unsettled": sum(
                    1 for v in in_period if v.views is not None and not v.settled
                ),
                "no_snapshot": sum(1 for v in in_period if v.views is None),
                "ambiguous_goal": len(ambiguous_goals(in_period, plan)),
            },
        },
        "channel": {
            "weekly": [
                {
                    "week": w.week.isoformat(),
                    "videos": w.videos,
                    "median_views": w.median_views,
                }
                for w in weekly_channel(in_period, since, until)
            ],
            "lost_uploads": asdict(lost_uploads(in_period, attempts)),
        },
        "rows": [_row(v, labels.get(v.record_id)) for v in in_period],
        "unlabelled": [v.record_id for v in in_period if v.record_id not in labels],
        "cycle_comparison": {
            "current": {
                **asdict(comparison.current),
                "median_relative": _round(comparison.current.median_relative),
            },
            "previous": {
                **asdict(comparison.previous),
                "median_relative": _round(comparison.previous.median_relative),
            },
            "also_changed": comparison.also_changed,
            "verdict_possible": comparison.verdict_possible,
            "reason": comparison.reason,
        },
        "exploration": {
            "share_intended": plan.share,
            "share_since": plan.share_since.isoformat() if plan.share_since else None,
            "share_achieved": _round(share_achieved(videos, plan)),
            "slots": slots,
            "filled": filled,
            "experiments": [
                {**asdict(p), "median_relative": _round(p.median_relative)}
                for p in experiment_progress(videos, plan, at.date())
            ],
        },
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Print the numbers of a tuning report as JSON.",
    )
    parser.add_argument(
        "--since", type=date.fromisoformat, help="First day (YYYY-MM-DD, local)."
    )
    parser.add_argument(
        "--until",
        type=date.fromisoformat,
        help="Last day, included (default: today).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Days ending on --until, when --since is not given (default: 30).",
    )
    parser.add_argument("--json", metavar="FILE", help="Write the package to a file.")
    parser.add_argument(
        "--min-settled",
        type=int,
        default=30,
        help="Refuse with fewer settled videos in the period (default: 30).",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=3,
        help="Refuse when the last collection is older (default: 3).",
    )
    parser.add_argument(
        "--settle-days",
        type=int,
        default=7,
        help="Days between publishing and collection for a video to settle"
        " (default: 7).",
    )
    args = parser.parse_args(argv)

    at = now()
    until = args.until or at.date()
    since = args.since or until - timedelta(days=args.days - 1)
    if since > until:
        parser.error(f"--since {since} is after --until {until}")
    try:
        package = build(
            SqliteHistoryStore(history_db_path()),
            FileTuningRecords(Path(tuning_dir())),
            since=since,
            until=until,
            min_settled=args.min_settled,
            max_age_days=args.max_age_days,
            settle_days=args.settle_days,
            at=at,
        )
    except Refusal as exc:
        print(exc, file=sys.stderr)
        return 2
    except TuningError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1

    text = json.dumps(package, ensure_ascii=False, indent=2)
    if args.json:
        Path(args.json).write_text(text + "\n", encoding="utf-8")
        print(
            f"{len(package['rows'])} vídeos no período,"
            f" {package['videos']['considered']} assentados: {args.json}"
        )
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
