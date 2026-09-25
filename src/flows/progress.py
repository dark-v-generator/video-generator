"""How a flow reports progress, and the lock that keeps one daily run at a time."""

import asyncio
from typing import Awaitable, Callable

# One line for the operator: a Telegram message, a line on stdout.
Progress = Callable[[str], Awaitable[None]]


def short_error(exc: Exception, limit: int = 300) -> str:
    """An error as the operator reads it: at most *limit* characters."""
    text = str(exc)
    return text[:limit] + "…" if len(text) > limit else text


class RunLock:
    """Callers check ``locked`` and refuse a second run instead of queueing it."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    @property
    def locked(self) -> bool:
        return self._lock.locked()

    async def __aenter__(self) -> "RunLock":
        await self._lock.acquire()
        return self

    async def __aexit__(self, *exc_info) -> None:
        self._lock.release()
