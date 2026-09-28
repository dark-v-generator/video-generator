"""Where the history lives, read from the environment on each call so tests
and the golden can point it at a temporary directory.

Kept apart from the container on purpose: the performance report opens the
history without importing the model, speech and browser libraries.
"""

import os

DEFAULT_HISTORY_DB_PATH = ".storage/history.sqlite"


def history_db_path() -> str:
    return os.environ.get("HISTORY_DB_PATH", DEFAULT_HISTORY_DB_PATH)
