"""Where the call-to-action starts in a narration."""

CTA_START_WORDS = {
    "curta",
    "like",
    "dale",
    "deja",
    "laisse",
    "lascia",
    "gib",
}


def _normalize_marker_word(word: str) -> str:
    return word.strip().lower().strip(".,!?;:¿¡")


def compute_cta_start(segments: list[dict]) -> float:
    """Find when the call-to-action starts in a single-story video.

    The title is not narrated, so there is no spoken intro to detect —
    only the CTA, found by looking for "curta" in the last ~20 words.
    Times are relative to the narration; the composer shifts them when it
    puts the cover in front.
    """
    n = len(segments)
    if n == 0:
        return 0.0

    cta_start_time = segments[-3]["start"] if n > 3 else segments[0]["start"]
    for i in range(max(0, n - 20), n):
        word = _normalize_marker_word(segments[i].get("word", ""))
        if word in CTA_START_WORDS:
            return segments[i]["start"]

    return cta_start_time
