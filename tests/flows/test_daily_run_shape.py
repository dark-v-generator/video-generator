"""The daily flow stays one short module with no channel or file-layout detail (SC-009)."""

import re
from pathlib import Path

DAILY_RUN = Path(__file__).parents[2] / "src" / "flows" / "daily_run.py"


def test_daily_run_fits_in_300_lines():
    assert len(DAILY_RUN.read_text().splitlines()) <= 300


def test_daily_run_knows_nothing_of_telegram_the_terminal_or_file_paths():
    offending = [
        line
        for line in DAILY_RUN.read_text().splitlines()
        if re.search(r"telegram|argparse|os\.path|open\(", line)
    ]
    assert offending == []
