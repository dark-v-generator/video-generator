"""Canonical list of forbidden strong words.

Single source of truth for the strong-words guard tests. Mirrors the
"Absolutely forbidden word families" section of the strong-words policy in
``src/proxies/prompts/two_part_story.jinja2`` (and the equivalent policy in the
single-part and DSPy paths). If that policy changes, update this list so the
guard tests stay aligned with the prompt.
"""

# Terms that must never appear in a title or narration. Kept lowercase; the
# guard matches case-insensitively with word boundaries so that inflected or
# compound Portuguese words (e.g. "amortecer" vs "morte") do not trigger false
# positives.
FORBIDDEN_WORDS = [
    # Death / violence
    "matar",
    "morrer",
    "morto",
    "morte",
    "assassinar",
    "suicídio",
    "suicidou",
    "atirar",
    "esfaquear",
    "sangue",
    "sangrento",
    "kill",
    "murder",
    "die",
    "dead",
    "suicide",
    "shoot",
    "stab",
    "blood",
    # Drugs
    "droga",
    "drogas",
    "cocaína",
    "maconha",
    "viciado",
    "drogado",
    "drugs",
    "cocaine",
    "weed",
    "crack",
    "junkie",
    # Sexual
    "transar",
    "transou",
    "transa",
    "sexo explícito",
    "estuprar",
    "estupro",
    "abuso sexual",
    "rape",
    "sexually assault",
    # Weapons
    "arma de fogo",
    "pistola",
    "fuzil",
    "gun",
    "firearm",
    "pistol",
]
