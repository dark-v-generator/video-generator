"""Availability checks for Reddit posts returned by scraping/API endpoints."""

from __future__ import annotations

import re
from typing import Any


_UNAVAILABLE_EXACT_TEXT = {
    "[deleted]",
    "[removed]",
    "[unavailable]",
    "deleted",
    "removed",
    "unavailable",
    "post unavailable",
    "this post is unavailable",
    "this content is unavailable",
    "this post is no longer available",
    "this content is no longer available",
    "sorry, this post is no longer available",
}

_UNAVAILABLE_PATTERNS = (
    re.compile(r"^this (?:post|content) (?:has been|was) (?:deleted|removed)\.?$"),
    re.compile(r"^removed by (?:reddit|moderators|the moderators)\.?$"),
)


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split()).lower()


def is_unavailable_reddit_text(value: Any) -> bool:
    text = _normalize_text(value)
    if not text:
        return False
    return text in _UNAVAILABLE_EXACT_TEXT or any(
        pattern.match(text) for pattern in _UNAVAILABLE_PATTERNS
    )


def is_unavailable_reddit_post(title: Any, content: Any) -> bool:
    return is_unavailable_reddit_text(title) or is_unavailable_reddit_text(content)


def is_unavailable_reddit_post_data(post_data: dict[str, Any]) -> bool:
    if post_data.get("removed_by_category"):
        return True
    return is_unavailable_reddit_post(
        post_data.get("title", ""),
        post_data.get("selftext", ""),
    )


def _unavailable_message(url: str | None = None) -> str:
    source = f" ({url})" if url else ""
    return f"Reddit post is unavailable or removed; skipping{source}."


def assert_reddit_post_data_available(
    post_data: dict[str, Any], url: str | None = None
) -> None:
    if is_unavailable_reddit_post_data(post_data):
        raise ValueError(_unavailable_message(url))


def assert_reddit_post_available(title: Any, content: Any, url: str | None = None) -> None:
    if not is_unavailable_reddit_post(title, content):
        return

    raise ValueError(_unavailable_message(url))
