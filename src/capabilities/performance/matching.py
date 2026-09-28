"""Which record each TikTok video came from, by caption and slot.

The caption TikTok shows is the record's title plus hashtags, so the two are
compared with the hashtags stripped, and with accents, quotes and punctuation
folded: on the server's account "café" came back "cafe" and curly quotes came
back straight. A story published again after a failure has two records with
the same title; the slot each was scheduled for tells them apart. What still
cannot be told apart is reported, never guessed.
"""

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

import unidecode

from ...entities.history import PublishedRecord, TikTokVideoStats
from ..publishing import strip_trailing_hashtags

DEFAULT_MAX_GAP = timedelta(hours=12)


@dataclass(frozen=True)
class MatchResult:
    matched: dict[int, TikTokVideoStats]  # record id -> video
    unmatched: list[TikTokVideoStats]
    # Each ambiguous video with the ids of the records it could belong to.
    ambiguous: list[tuple[TikTokVideoStats, list[int]]]


def normalize_caption(text: str) -> str:
    folded = unidecode.unidecode(strip_trailing_hashtags(text)).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", folded).split())


def match(
    records: list[PublishedRecord],
    videos: list[TikTokVideoStats],
    *,
    max_gap: timedelta = DEFAULT_MAX_GAP,
) -> MatchResult:
    by_id = {
        p.record.tiktok_video_id: p.record.id
        for p in records
        if p.record.tiktok_video_id
    }
    # A record that already knows its video is not up for a caption match.
    by_caption: dict[str, list[PublishedRecord]] = defaultdict(list)
    for p in records:
        if not p.record.tiktok_video_id:
            by_caption[normalize_caption(p.record.title)].append(p)

    claims: dict[int, list[TikTokVideoStats]] = defaultdict(list)
    unmatched: list[TikTokVideoStats] = []
    ambiguous: list[tuple[TikTokVideoStats, list[int]]] = []
    for video in videos:
        if video.video_id in by_id:
            claims[by_id[video.video_id]].append(video)
            continue
        candidates = by_caption.get(normalize_caption(video.description), [])
        if len(candidates) > 1:
            near = [p for p in candidates if _near(p, video, max_gap)]
            if len(near) != 1:
                ambiguous.append((video, [p.record.id for p in candidates]))
                continue
            candidates = near
        if not candidates:
            unmatched.append(video)
            continue
        claims[candidates[0].record.id].append(video)

    matched: dict[int, TikTokVideoStats] = {}
    for record_id, claimants in claims.items():
        if len(claimants) == 1:
            matched[record_id] = claimants[0]
        else:
            # The same record twice: a real re-post, the operator decides.
            ambiguous.extend((video, [record_id]) for video in claimants)
    return MatchResult(matched=matched, unmatched=unmatched, ambiguous=ambiguous)


def _near(p: PublishedRecord, video: TikTokVideoStats, max_gap: timedelta) -> bool:
    if p.scheduled_at is None or video.created_at is None:
        return False
    return abs(video.created_at - p.scheduled_at) < max_gap
