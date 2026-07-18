"""Guard tests for hook quality and the frozen output contract.

These are deterministic guards over the static few-shot examples and the
two-part output contract. They do NOT test LLM generation (non-deterministic);
hook quality itself is verified by manual review of a sample plus the "gancho"
score comparison described in the feature quickstart.

Shared helpers live here so both Milestone 1 (two-part path) and Milestone 2
(single-part / DSPy paths) guards can reuse them.
"""

import os
import re

import yaml

from tests.services.forbidden_words import FORBIDDEN_WORDS

_EXAMPLES_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "src",
    "proxies",
    "examples",
    "two_part_story.yaml",
)

# Localized markers / CTA for the active (pt-br) few-shot examples.
PART1_MARKER = ". Parte 1."
PART2_MARKER = ". Parte 2."
PART1_CTA = "Curta e me siga para a parte 2."


def load_two_part_examples():
    """Load the two-part few-shot examples from the canonical YAML file."""
    with open(_EXAMPLES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert data, "two_part_story.yaml must contain at least one example"
    return data


def _find_forbidden(text):
    """Return the forbidden terms present in ``text`` (word-boundary match)."""
    lowered = text.lower()
    hits = []
    for word in FORBIDDEN_WORDS:
        pattern = r"\b" + re.escape(word.lower()) + r"\b"
        if re.search(pattern, lowered):
            hits.append(word)
    return hits


def assert_no_forbidden_words(text):
    """Assert ``text`` contains no term from the strong-words policy."""
    hits = _find_forbidden(text)
    assert not hits, f"forbidden word(s) present: {hits}"


def assert_two_part_structure(entry):
    """Assert the two-part markers and the end-of-part-1 CTA are present.

    Both ``part1`` and ``part2`` must start with the explicit ``title`` followed
    by the localized marker, and ``part1`` must end with the part-2 CTA.
    """
    title = entry["title"]
    part1 = entry["part1"].strip()
    part2 = entry["part2"].strip()

    assert part1.startswith(title + PART1_MARKER), (
        f"part1 must start with '{title}{PART1_MARKER}'"
    )
    assert part2.startswith(title + PART2_MARKER), (
        f"part2 must start with '{title}{PART2_MARKER}'"
    )
    assert part1.endswith(PART1_CTA), (
        f"part1 must end with the part-2 CTA '{PART1_CTA}'"
    )


# --- Milestone 1: two-part active path guards -------------------------------


def test_examples_have_explicit_title_matching_part1_prefix():
    """Each example exposes a `title` equal to the part1 hook before the marker."""
    for entry in load_two_part_examples():
        assert entry.get("title"), "every example must define a non-empty `title`"
        prefix = entry["part1"].split(PART1_MARKER)[0].strip()
        assert entry["title"] == prefix, (
            f"title must equal the part1 prefix before '{PART1_MARKER}': "
            f"{entry['title']!r} != {prefix!r}"
        )


def test_examples_have_no_forbidden_words():
    for entry in load_two_part_examples():
        assert_no_forbidden_words(entry["title"])
        assert_no_forbidden_words(entry["part1"])
        assert_no_forbidden_words(entry["part2"])


def test_examples_preserve_two_part_structure():
    for entry in load_two_part_examples():
        assert_two_part_structure(entry)
