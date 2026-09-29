"""What the channel did in the period, whatever the stories were (US1): its
reach week by week and the videos it lost on the way to TikTok."""

from datetime import timedelta

from src.capabilities.tuning import Video, lost_uploads, weekly_channel

from .tuning_videos import DAY0, at, failed, row, scheduled, video

# 2026-09-01 is a Tuesday: its week starts on Monday, 2026-08-31.
MONDAY = DAY0 - timedelta(days=1)


def test_each_week_has_its_videos_and_their_median_views():
    videos = [
        video(1, day=0, views=100),
        video(2, day=1, views=300),
        video(3, day=2, views=1000),
        video(4, day=7, views=50),
        video(5, day=8, views=None, settled=False),  # not collected yet
    ]

    weeks = weekly_channel(videos, DAY0, DAY0 + timedelta(days=8))

    assert [(w.week, w.videos, w.median_views) for w in weeks] == [
        (MONDAY, 3, 300),
        (MONDAY + timedelta(days=7), 2, 50),
    ]


def test_a_week_without_videos_shows_as_empty():
    videos = [video(1, day=0, views=100), video(2, day=14, views=200)]

    weeks = weekly_channel(videos, DAY0, DAY0 + timedelta(days=18))

    assert [(w.videos, w.median_views) for w in weeks] == [
        (1, 100),
        (0, None),
        (1, 200),
    ]


def test_a_video_never_published_is_not_in_any_week():
    unpublished = Video(row=row(9, created=at(1)), published_at=None, settled=False)

    weeks = weekly_channel([unpublished], DAY0, DAY0)

    assert [(w.videos, w.median_views) for w in weeks] == [(0, None)]


def test_lost_uploads_count_failed_attempts_and_videos_never_published():
    published = Video(
        row=row(1, views=10, taken=at(9)), published_at=at(1), settled=True
    )
    retried = Video(row=row(2, views=10, taken=at(9)), published_at=at(2), settled=True)
    lost = Video(row=row(3), published_at=None, settled=False)
    attempts = {
        1: [scheduled(at(1))],
        2: [failed(at(1.5)), scheduled(at(2))],
        3: [failed(at(3)), failed(at(3.1))],
    }

    lost_count = lost_uploads([published, retried, lost], attempts)

    assert (lost_count.attempts_failed, lost_count.never_published) == (3, 1)
