"""Guard tests for hook quality and the frozen output contract.

These are deterministic guards over the static few-shot examples and the
two-part output contract. They do NOT test LLM generation (non-deterministic);
hook quality itself is verified by manual review of a sample plus the "gancho"
score comparison described in the feature quickstart.

Contract note (repair 2026-07-18, FR-014/FR-015): the `title` is the hook shown
on the COVER and is NOT narrated. `part1`/`part2` begin directly in the story —
they must NOT start with the title nor with a "Parte N." marker.
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

PART1_CTA = "Curta e me siga para a parte 2."
# Markers that must NOT be spoken (they live on the cover, not the narration).
PART_MARKERS = ("Parte 1.", "Parte 2.")


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


def assert_narration_starts_in_story(entry):
    """Assert the narration begins in the story, not on the title/marker.

    Neither ``part1`` nor ``part2`` may start with the (cover-only) title, and
    neither may open with a "Parte N." marker in its first words.
    """
    title = entry["title"]
    for key in ("part1", "part2"):
        text = entry[key].strip()
        assert not text.startswith(title), (
            f"{key} must not start with the title (title is cover-only, not narrated)"
        )
        head = text[:40]
        for marker in PART_MARKERS:
            assert marker not in head, (
                f"{key} must not open with the spoken marker '{marker}'"
            )


# --- Milestone 1 + repair: two-part active path guards ----------------------


def test_examples_have_cover_title():
    """Each example exposes a non-empty `title` used as the cover hook."""
    for entry in load_two_part_examples():
        assert entry.get("title"), "every example must define a non-empty `title`"


def test_examples_have_no_forbidden_words():
    for entry in load_two_part_examples():
        assert_no_forbidden_words(entry["title"])
        assert_no_forbidden_words(entry["part1"])
        assert_no_forbidden_words(entry["part2"])


def test_narration_excludes_title_and_marker():
    for entry in load_two_part_examples():
        assert_narration_starts_in_story(entry)


def test_part1_ends_with_cta():
    for entry in load_two_part_examples():
        assert entry["part1"].strip().endswith(PART1_CTA), (
            f"part1 must end with the part-2 CTA '{PART1_CTA}'"
        )
