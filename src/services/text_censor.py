import re
import unicodedata
from typing import Optional

from ..entities.captions import CaptionSegment

_VOWEL_MAP: dict[str, str] = {"a": "4", "e": "3", "i": "1", "o": "0"}

# Stems used as prefix patterns: \b<stem>\w* catches the stem and all its inflections.
# Sorted longest-first so longer stems are tried before shorter prefixes they contain.
_DEFAULT_STEMS: list[str] = sorted(
    [
        # Portuguese — death / violence
        "assassinar",
        "assassinou",
        "esfaquear",
        "esfaqueou",
        "sangrento",
        "sangramento",
        "sangue",
        "suicidou",
        "suicidio",
        "suicídio",
        "matar",
        "matou",
        "mata",
        "mato",
        "morrer",
        "morreu",
        "morto",
        "morta",
        "morte",
        "atirar",
        "atirou",
        # Portuguese — drugs
        "cocaina",
        "cocaína",
        "maconha",
        "drogado",
        "droga",
        "drogas",
        # Portuguese — sexual
        "estuprar",
        "estuprou",
        "estupro",
        "transar",
        "transou",
        "transa",
        "sexo",
        # Portuguese — weapons
        "arma",
        # Portuguese — crime
        "crime",
        "criminoso",
        # English — death / violence
        "murdered",
        "murder",
        "killing",
        "killed",
        "kills",
        "kill",
        "stabbed",
        "stabbing",
        "shooting",
        "suicide",
        "blood",
        "dead",
        "died",
        # English — drugs
        "cocaine",
        "drugs",
        "weed",
        # English — sexual
        "raped",
        "rape",
        "raping",
        "sex",
        # English — weapons
        "gun",
        "shot",
    ],
    key=len,
    reverse=True,
)


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _obfuscate(word: str) -> str:
    """Derive an obfuscated form: replace vowels with look-alike digits and insert '*' at midpoint."""
    chars: list[str] = []
    for ch in word:
        lower = ch.lower()
        if lower in _VOWEL_MAP:
            chars.append(_VOWEL_MAP[lower])
        else:
            chars.append(ch)

    mid = len(chars) // 2
    chars.insert(mid, "*")
    return "".join(chars)


class TextCensor:
    """
    Replaces flagged words in visible on-screen text with obfuscated equivalents.

    Matching is case-insensitive and accent-insensitive (the accented form of a stem
    will still be caught).  Each stem is matched as a whole-token prefix so conjugations
    (e.g. "matarmos" from stem "matar") are also caught.  The replacement preserves the
    original word's casing for non-vowel characters.

    Designed to be applied ONLY to visible text (cover titles, caption segments, JSON
    exports).  Never apply to the text fed to the TTS engine — euphemisms in the LLM
    prompt handle audio moderation.
    """

    def __init__(self, extra_mappings: Optional[dict[str, str]] = None) -> None:
        self._overrides: dict[str, str] = {}
        if extra_mappings:
            self._overrides = {_strip_accents(k.lower()): v for k, v in extra_mappings.items()}

        stems = list(_DEFAULT_STEMS)
        if extra_mappings:
            stems.extend(extra_mappings.keys())

        self._patterns: list[re.Pattern] = [
            re.compile(
                r"\b" + re.escape(_strip_accents(stem.lower())) + r"\w*",
                re.IGNORECASE | re.UNICODE,
            )
            for stem in stems
        ]

    def censor(self, text: str) -> str:
        if not text:
            return text

        normalized = _strip_accents(text)

        matches: list[tuple[int, int]] = []
        for pattern in self._patterns:
            for m in pattern.finditer(normalized):
                matches.append((m.start(), m.end()))

        if not matches:
            return text

        # Sort by position; deduplicate overlaps (first / leftmost match wins).
        matches.sort()
        merged: list[tuple[int, int]] = []
        for start, end in matches:
            if merged and start < merged[-1][1]:
                continue
            merged.append((start, end))

        # Apply replacements right-to-left so earlier indices remain valid.
        result = text
        for start, end in reversed(merged):
            original_word = text[start:end]
            replacement = self._replace(original_word)
            result = result[:start] + replacement + result[end:]

        return result

    def censor_segments(self, segments: list[CaptionSegment]) -> list[CaptionSegment]:
        return [
            CaptionSegment(start=s.start, end=s.end, text=self.censor(s.text))
            for s in segments
        ]

    def censor_word_dicts(self, word_dicts: list[dict]) -> list[dict]:
        """Censor the 'word' key in a list of transcription dicts."""
        return [
            {**d, "word": self.censor(d["word"])} if "word" in d else d
            for d in word_dicts
        ]

    def _replace(self, word: str) -> str:
        key = _strip_accents(word.lower())
        if key in self._overrides:
            return self._overrides[key]
        return _obfuscate(word)
