"""The server-side queue of story packages prepared on the laptop.

A package's state is the directory it sits in — ``inbox/`` waiting, ``done/``
produced, ``failed/`` rejected — so the operator can see and fix the queue with
``ls`` and ``mv``, and a crash mid-run leaves the package exactly where it was.
This is the one service allowed to touch the filesystem: the directory *is* the
data model.
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import ValidationError

from src.core.logging_config import get_logger
from src.entities.prepared_story import PreparedStoryPackage

logger = get_logger(__name__)

INBOX = "inbox"
DONE = "done"
FAILED = "failed"


@dataclass
class QueuedPackage:
    """A package file in ``inbox/``, with the mtime that orders the queue."""

    path: str
    package: PreparedStoryPackage
    mtime: float


class PreparedStoryQueue:
    def __init__(self, root: str):
        self._root = root
        self.last_rejections: List[Tuple[str, str]] = []

    @property
    def root(self) -> str:
        return self._root

    def _dir(self, state: str) -> str:
        path = os.path.join(self._root, state)
        os.makedirs(path, exist_ok=True)
        return path

    def list_inbox(self) -> List[QueuedPackage]:
        """Packages waiting to be produced, oldest first.

        A file that does not parse is moved to ``failed/`` right here instead of
        failing the daily run: one malformed package should not cost the
        operator the whole queue. The rejections are kept in
        ``last_rejections`` so the caller can report them.
        """
        # All three states are created together so that a plain `ls` on the
        # server shows the operator where a package can be.
        inbox, _, _ = (self._dir(INBOX), self._dir(DONE), self._dir(FAILED))
        self.last_rejections = []
        items: List[QueuedPackage] = []

        for name in sorted(os.listdir(inbox)):
            if not name.endswith(".json"):
                continue

            path = os.path.join(inbox, name)
            try:
                with open(path, encoding="utf-8") as f:
                    package = PreparedStoryPackage.model_validate_json(f.read())
            except (ValidationError, ValueError, OSError) as exc:
                error = f"{name}: {exc}"
                logger.warning("Rejecting prepared package %s: %s", path, exc)
                self.last_rejections.append((name, str(exc)))
                self._move(path, FAILED, ".error.txt", error)
                continue

            items.append(
                QueuedPackage(
                    path=path,
                    package=package,
                    mtime=os.path.getmtime(path),
                )
            )

        items.sort(key=lambda item: (item.mtime, os.path.basename(item.path)))
        return items

    def mark_done(self, item: QueuedPackage, outcome: Dict[str, Any]) -> str:
        return self._move(
            item.path,
            DONE,
            ".outcome.json",
            json.dumps(outcome, ensure_ascii=False, indent=2),
        )

    def mark_failed(self, item: QueuedPackage, error: str) -> str:
        return self._move(item.path, FAILED, ".error.txt", error)

    def known_post_urls(self) -> Set[str]:
        """Post URLs already queued or produced, to keep discovery off them."""
        urls: Set[str] = set()
        for state in (INBOX, DONE):
            for name in sorted(os.listdir(self._dir(state))):
                if not name.endswith(".json") or name.endswith(".outcome.json"):
                    continue
                path = os.path.join(self._dir(state), name)
                try:
                    with open(path, encoding="utf-8") as f:
                        package = PreparedStoryPackage.model_validate_json(f.read())
                except (ValidationError, ValueError, OSError):
                    # Reporting belongs to list_inbox; here a bad file simply
                    # excludes nothing.
                    continue
                if package.post.url:
                    urls.add(package.post.url)
        return urls

    def _move(
        self,
        path: str,
        state: str,
        sidecar_suffix: str,
        sidecar_content: Optional[str],
    ) -> str:
        base = os.path.splitext(os.path.basename(path))[0]
        target = os.path.join(self._dir(state), f"{base}.json")
        os.replace(path, target)

        if sidecar_content is not None:
            sidecar = os.path.join(self._dir(state), f"{base}{sidecar_suffix}")
            with open(sidecar, "w", encoding="utf-8") as f:
                f.write(sidecar_content)

        return target
