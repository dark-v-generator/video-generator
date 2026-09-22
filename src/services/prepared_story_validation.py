"""Local validation of a prepared story package, before it reaches the server.

The forbidden-word check reuses ``TextCensor`` as a detector rather than
keeping a second word list: the local check and the production censorship then
agree by construction. The censor never rewrites anything here.
"""

import re
from typing import List

from src.entities.language import Language
from src.entities.prepared_story import PreparedStoryPackage
from src.services.text_censor import TextCensor

_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)
_CONTEXT_CHARS = 40


def _context(text: str, start: int, end: int) -> str:
    left = max(0, start - _CONTEXT_CHARS)
    right = min(len(text), end + _CONTEXT_CHARS)

    snippet = text[left:right]
    if left > 0:
        snippet = "..." + snippet
    if right < len(text):
        snippet = snippet + "..."
    return snippet


def _forbidden_words(field: str, text: str, censor: TextCensor) -> List[str]:
    problems: List[str] = []
    for match in _WORD_PATTERN.finditer(text):
        word = match.group()
        if censor.censor(word) != word:
            context = _context(text, match.start(), match.end())
            problems.append(f'{field}: {word!r} em "{context}"')
    return problems


def validate_package(
    package: PreparedStoryPackage,
    censor: TextCensor,
    expected_language: Language,
) -> List[str]:
    """Return every problem found, in reading order. Empty list means valid."""
    problems: List[str] = []

    if package.language is not expected_language:
        problems.append(
            f"language: package={package.language.value} "
            f"server={expected_language.value}"
        )

    problems.extend(_forbidden_words("story_title", package.story_title, censor))
    problems.extend(_forbidden_words("script_text", package.script_text, censor))

    if (
        package.narrator_gender in ("male", "female")
        and package.resolved_gender != package.narrator_gender
    ):
        problems.append(
            f"resolved_gender: '{package.resolved_gender}' não confere com "
            f"narrator_gender '{package.narrator_gender}'"
        )

    return problems
