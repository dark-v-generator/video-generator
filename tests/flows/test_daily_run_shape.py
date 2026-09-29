"""The daily flow stays one short module with no channel or file-layout detail (SC-009)."""

import re
from pathlib import Path

DAILY_RUN = Path(__file__).parents[2] / "src" / "flows" / "daily_run.py"


def test_daily_run_fits_in_320_lines():
    # 300 in feature 004; feature 005 adds one line per event the run reports
    # to its history (the bookkeeping itself lives in run_record.py).
    assert len(DAILY_RUN.read_text().splitlines()) <= 320


def test_daily_run_knows_nothing_of_telegram_the_terminal_or_file_paths():
    offending = [
        line
        for line in DAILY_RUN.read_text().splitlines()
        # The builtin open(), not a method such as the plan's open().
        if re.search(r"telegram|argparse|os\.path|(?<![.\w])open\(", line)
    ]
    assert offending == []
