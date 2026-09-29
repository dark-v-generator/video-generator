"""Where the history and the tuning records live, read from the environment on
each call so tests and the golden can point them at a temporary directory.

Kept apart from the container on purpose: the performance report opens the
history without importing the model, speech and browser libraries.
"""

import os

DEFAULT_HISTORY_DB_PATH = ".storage/history.sqlite"
DEFAULT_TUNING_DIR = "tuning"


def history_db_path() -> str:
    return os.environ.get("HISTORY_DB_PATH", DEFAULT_HISTORY_DB_PATH)


def tuning_dir() -> str:
    return os.environ.get("TUNING_DIR", DEFAULT_TUNING_DIR)
