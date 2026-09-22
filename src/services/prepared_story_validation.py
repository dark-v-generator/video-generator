"""Local validation of a prepared story package, before it reaches the server.

The forbidden-word check reuses ``TextCensor`` as a detector rather than
keeping a second word list: the local check and the production censorship then
agree by construction. The censor never rewrites anything here.
"""

import re
from typing import List, Tuple

from src.entities.language import Language
from src.entities.prepared_story import StoryPackage, TwoPartStoryPackage
from src.services.text_censor import TextCensor

_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)
_CONTEXT_CHARS = 40

# The closing line the two-part prompt fixes for each language. A language the
# prompt does not pin down is not checked: the rule belongs to the prompt, and
# inventing one here would fail packages the server would happily produce.
PART2_CTA = {
    Language.PORTUGUESE: "Curta e me siga para a parte 2.",
}


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


def _script_fields(package: StoryPackage) -> List[Tuple[str, str]]:
    if isinstance(package, TwoPartStoryPackage):
        return [("part1_text", package.part1_text), ("part2_text", package.part2_text)]
    return [("script_text", package.script_text)]


def validate_package(
    package: StoryPackage,
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

    for field, text in _script_fields(package):
        problems.extend(_forbidden_words(field, text, censor))

        if field == "part1_text":
            cta = PART2_CTA.get(package.language)
            if cta and not text.rstrip().endswith(cta):
                problems.append(f'part1_text: precisa terminar com "{cta}"')

    if (
        package.narrator_gender in ("male", "female")
        and package.resolved_gender != package.narrator_gender
    ):
        problems.append(
            f"resolved_gender: '{package.resolved_gender}' não confere com "
            f"narrator_gender '{package.narrator_gender}'"
        )

    return problems
