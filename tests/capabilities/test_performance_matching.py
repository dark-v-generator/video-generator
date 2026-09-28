"""Matching TikTok videos to records: the five rules of the contract."""

from datetime import datetime, timedelta, timezone

from src.capabilities.performance import match, normalize_caption
from src.entities.history import (
    PerformanceMetrics,
    PublishedRecord,
    TikTokVideoStats,
    VideoRecord,
)

SLOT = datetime(2026, 9, 20, 21, 0, tzinfo=timezone.utc)
TAGS = "  #fyp  #storytime  #reddit"


def published(record_id, title, *, slot=SLOT, tiktok_video_id=None):
    return PublishedRecord(
        record=VideoRecord(
            id=record_id,
            created_at=SLOT - timedelta(hours=8),
            run_id=None,
            video_path=f"out/story_{record_id:02d}.mp4",
            title=title,
            summary="",
            post_url=f"https://reddit.com/p{record_id}",
            tiktok_video_id=tiktok_video_id,
        ),
        scheduled_at=slot,
    )


def video(video_id, description, *, posted=SLOT):
    return TikTokVideoStats(
        video_id=video_id,
        description=description,
        created_at=posted,
        metrics=PerformanceMetrics(views=10),
    )


def test_the_caption_loses_its_trailing_hashtags_spaces_and_case():
    assert (
        normalize_caption("Minha mãe  botou o volume no TALO  #fyp #storytime")
        == "minha mãe botou o volume no talo"
    )
    # A hashtag inside the sentence is part of the title.
    assert normalize_caption("O #1 da turma #fyp") == "o #1 da turma"


def test_a_record_that_knows_its_video_id_matches_it_whatever_the_caption():
    records = [published(1, "Old title", tiktok_video_id="v1")]

    result = match(records, [video("v1", "Edited caption on TikTok" + TAGS)])

    assert result.matched == {1: video("v1", "Edited caption on TikTok" + TAGS)}
    assert result.unmatched == result.ambiguous == []


def test_the_published_caption_matches_the_title_with_hashtags_and_other_case():
    records = [published(1, "A vizinha e o bolo"), published(2, "Outro título")]

    result = match(records, [video("v1", "A VIZINHA e o bolo" + TAGS)])

    assert list(result.matched) == [1]
    assert result.matched[1].video_id == "v1"


def test_a_republished_story_is_told_apart_by_its_slot():
    records = [
        published(1, "Mesma história", slot=SLOT - timedelta(days=2)),
        published(2, "Mesma história", slot=SLOT),
    ]

    result = match(
        records,
        [video("v1", "Mesma história" + TAGS, posted=SLOT + timedelta(minutes=3))],
        max_gap=timedelta(hours=12),
    )

    assert list(result.matched) == [2]
    assert result.ambiguous == []


def test_two_candidates_neither_near_the_post_time_are_ambiguous():
    records = [
        published(1, "Mesma história", slot=SLOT - timedelta(days=2)),
        published(2, "Mesma história", slot=SLOT - timedelta(days=1)),
    ]
    tiktok = video("v1", "Mesma história" + TAGS)

    result = match(records, [tiktok], max_gap=timedelta(hours=12))

    assert result.matched == {}
    assert result.ambiguous == [(tiktok, [1, 2])]


def test_a_video_no_record_has_the_caption_of_is_unmatched():
    tiktok = video("v9", "Postado à mão" + TAGS)

    result = match([published(1, "A vizinha e o bolo")], [tiktok])

    assert result.matched == {}
    assert result.unmatched == [tiktok]


def test_two_videos_on_one_record_are_both_ambiguous():
    first = video("v1", "A vizinha e o bolo" + TAGS)
    second = video("v2", "A vizinha e o bolo" + TAGS, posted=SLOT + timedelta(hours=1))

    result = match([published(1, "A vizinha e o bolo")], [first, second])

    assert result.matched == {}
    assert result.ambiguous == [(first, [1]), (second, [1])]


def test_a_record_with_a_video_id_is_not_offered_to_another_video_by_caption():
    records = [published(1, "A vizinha e o bolo", tiktok_video_id="v1")]
    repost = video("v2", "A vizinha e o bolo" + TAGS)

    result = match(records, [repost])

    assert result.matched == {}
    assert result.unmatched == [repost]
