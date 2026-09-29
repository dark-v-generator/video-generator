"""A video's views against the settled videos published around it (US1,
FR-013): the channel's reach moves week to week, the neighbours move with it."""

import pytest

from src.capabilities.tuning import measure, published_at, settled

from .tuning_videos import at, failed, row, scheduled


def _channel(views: list[int], *, collected_day: float = 60) -> tuple[list, dict]:
    """One video a day, each published on its day and collected on
    ``collected_day``."""
    rows = [
        row(i, created=at(i), views=v, taken=at(collected_day))
        for i, v in enumerate(views, start=1)
    ]
    attempts = {i: [scheduled(at(i))] for i in range(1, len(views) + 1)}
    return rows, attempts


def _by_id(videos) -> dict:
    return {v.record_id: v for v in videos}


def test_a_video_is_measured_against_five_neighbours_on_each_side():
    views = [100] * 5 + [300] + [100] * 5
    views[0] = 1_000_000  # a viral neighbour does not move the median
    videos = _by_id(measure(*_channel(views)))

    assert videos[6].neighbours == 10
    assert videos[6].relative == pytest.approx(3.0)


def test_at_the_edge_the_neighbours_all_come_from_one_side():
    views = [500] + [100] * 10 + [1_000_000]
    videos = _by_id(measure(*_channel(views)))

    assert videos[1].neighbours == 10
    assert videos[1].relative == pytest.approx(5.0)  # the 12th is not among them
    # Two before, so eight after.
    assert videos[3].neighbours == 10


def test_with_fewer_than_five_neighbours_there_is_no_relative():
    videos = measure(*_channel([100, 200, 300, 400, 500]))

    assert all(v.settled for v in videos)
    assert [v.neighbours for v in videos] == [4] * 5
    assert [v.relative for v in videos] == [None] * 5


def test_videos_published_at_the_same_time_are_each_others_neighbours():
    rows, attempts = _channel([100] * 10)
    rows.append(row(11, created=at(5), views=400, taken=at(60)))
    attempts[11] = [scheduled(at(5))]  # the same slot as video 5
    videos = _by_id(measure(rows, attempts))

    assert videos[11].neighbours == 10
    assert videos[11].relative == pytest.approx(4.0)
    assert videos[5].relative == pytest.approx(1.0)


def test_a_video_is_never_its_own_neighbour():
    videos = _by_id(measure(*_channel([1000, 100, 100, 200, 300, 300])))

    # The median of the five others is 200; with its own 1000 it would be 250.
    assert videos[1].neighbours == 5
    assert videos[1].relative == pytest.approx(5.0)


def test_a_video_without_numbers_is_no_one_s_neighbour():
    rows, attempts = _channel([100] * 5 + [300] + [100] * 5)
    rows.append(row(12, created=at(5.5)))  # never collected
    attempts[12] = [scheduled(at(5.5))]
    videos = _by_id(measure(rows, attempts))

    assert videos[12].settled is False
    assert videos[12].relative is None
    assert videos[6].neighbours == 10
    assert videos[6].relative == pytest.approx(3.0)


def test_an_unsettled_video_has_no_relative_and_is_no_one_s_neighbour():
    rows, attempts = _channel([100] * 5 + [300] + [100] * 5, collected_day=12)
    videos = _by_id(measure(rows, attempts))

    # Collected on day 12: videos 1 to 5 had seven days, 6 to 11 did not.
    assert [videos[i].settled for i in range(1, 12)] == [True] * 5 + [False] * 6
    assert videos[6].relative is None
    assert videos[1].neighbours == 4
    assert videos[1].relative is None


def test_settled_is_counted_to_the_collection_not_to_today():
    # Published on day 0; today is long after, but the numbers are from day 3.
    assert settled(at(0), at(3), 7) is False
    assert settled(at(0), at(7), 7) is True
    assert settled(at(0), None, 7) is False
    assert settled(None, at(30), 7) is False


def test_a_video_is_published_at_its_newest_scheduled_slot():
    collected = row(1, views=10, taken=at(20), tiktok_created=at(2.5))

    assert published_at(collected, [scheduled(at(1)), scheduled(at(2))]) == at(2)
    assert published_at(collected, [scheduled(at(1)), failed(at(2))]) == at(1)
    # The publisher said it failed, but TikTok has the video.
    assert published_at(collected, [failed(at(2))]) == at(2.5)
    assert published_at(row(2), [failed(at(2))]) is None
