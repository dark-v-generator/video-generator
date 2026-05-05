"""Tests for the daily auto-publish schedule slot computation."""

import datetime

import pytest

from bots.satisfying_bot import compute_publish_slots, next_publish_slot


SLOTS = ["11:00", "13:00", "18:00", "20:00"]


class TestComputePublishSlots:
    def test_noon_picks_today_late_then_tomorrow_early(self):
        now = datetime.datetime(2026, 5, 5, 12, 0)
        result = compute_publish_slots(now, SLOTS, count=4, min_lead_minutes=30)

        assert result == [
            datetime.datetime(2026, 5, 5, 13, 0),
            datetime.datetime(2026, 5, 5, 18, 0),
            datetime.datetime(2026, 5, 5, 20, 0),
            datetime.datetime(2026, 5, 6, 11, 0),
        ]

    def test_early_morning_picks_all_today(self):
        now = datetime.datetime(2026, 5, 5, 7, 0)
        result = compute_publish_slots(now, SLOTS, count=4, min_lead_minutes=30)

        assert result == [
            datetime.datetime(2026, 5, 5, 11, 0),
            datetime.datetime(2026, 5, 5, 13, 0),
            datetime.datetime(2026, 5, 5, 18, 0),
            datetime.datetime(2026, 5, 5, 20, 0),
        ]

    def test_late_night_wraps_to_next_day(self):
        now = datetime.datetime(2026, 5, 5, 21, 0)
        result = compute_publish_slots(now, SLOTS, count=4, min_lead_minutes=30)

        assert result == [
            datetime.datetime(2026, 5, 6, 11, 0),
            datetime.datetime(2026, 5, 6, 13, 0),
            datetime.datetime(2026, 5, 6, 18, 0),
            datetime.datetime(2026, 5, 6, 20, 0),
        ]

    def test_lead_time_skips_close_slot(self):
        now = datetime.datetime(2026, 5, 5, 10, 45)
        result = compute_publish_slots(now, SLOTS, count=2, min_lead_minutes=30)

        assert result[0] == datetime.datetime(2026, 5, 5, 13, 0)

    def test_count_less_than_slots(self):
        now = datetime.datetime(2026, 5, 5, 7, 0)
        result = compute_publish_slots(now, SLOTS, count=2, min_lead_minutes=30)

        assert len(result) == 2
        assert result == [
            datetime.datetime(2026, 5, 5, 11, 0),
            datetime.datetime(2026, 5, 5, 13, 0),
        ]

    def test_count_exceeds_daily_slots_spans_days(self):
        now = datetime.datetime(2026, 5, 5, 7, 0)
        result = compute_publish_slots(now, SLOTS, count=6, min_lead_minutes=30)

        assert len(result) == 6
        assert result[4] == datetime.datetime(2026, 5, 6, 11, 0)
        assert result[5] == datetime.datetime(2026, 5, 6, 13, 0)

    def test_single_slot_config(self):
        now = datetime.datetime(2026, 5, 5, 12, 0)
        result = compute_publish_slots(now, ["18:00"], count=3, min_lead_minutes=30)

        assert result == [
            datetime.datetime(2026, 5, 5, 18, 0),
            datetime.datetime(2026, 5, 6, 18, 0),
            datetime.datetime(2026, 5, 7, 18, 0),
        ]

    def test_empty_slots_raises(self):
        now = datetime.datetime(2026, 5, 5, 12, 0)
        with pytest.raises(ValueError):
            compute_publish_slots(now, [], count=1, min_lead_minutes=30)

    def test_zero_lead_time(self):
        now = datetime.datetime(2026, 5, 5, 11, 0)
        result = compute_publish_slots(now, SLOTS, count=1, min_lead_minutes=0)

        assert result == [datetime.datetime(2026, 5, 5, 11, 0)]


class TestNextPublishSlot:
    """Tests for the incremental slot picker used during the publish loop."""

    def test_after_11_picks_13_same_day(self):
        after = datetime.datetime(2026, 5, 5, 11, 0)
        now = datetime.datetime(2026, 5, 5, 9, 0)
        result = next_publish_slot(after, SLOTS, min_lead_minutes=30, _now=now)
        assert result == datetime.datetime(2026, 5, 5, 13, 0)

    def test_after_20_wraps_to_next_day_11(self):
        after = datetime.datetime(2026, 5, 5, 20, 0)
        now = datetime.datetime(2026, 5, 5, 9, 0)
        result = next_publish_slot(after, SLOTS, min_lead_minutes=30, _now=now)
        assert result == datetime.datetime(2026, 5, 6, 11, 0)

    def test_sequential_calls_walk_forward(self):
        now = datetime.datetime(2026, 5, 5, 9, 0)
        s1 = next_publish_slot(now, SLOTS, min_lead_minutes=30, _now=now)
        s2 = next_publish_slot(s1, SLOTS, min_lead_minutes=30, _now=now)
        s3 = next_publish_slot(s2, SLOTS, min_lead_minutes=30, _now=now)
        s4 = next_publish_slot(s3, SLOTS, min_lead_minutes=30, _now=now)

        assert s1 == datetime.datetime(2026, 5, 5, 11, 0)
        assert s2 == datetime.datetime(2026, 5, 5, 13, 0)
        assert s3 == datetime.datetime(2026, 5, 5, 18, 0)
        assert s4 == datetime.datetime(2026, 5, 5, 20, 0)

    def test_lead_time_respected_against_real_clock(self):
        after = datetime.datetime(2026, 5, 5, 9, 0)
        now = datetime.datetime(2026, 5, 5, 12, 45)
        result = next_publish_slot(after, SLOTS, min_lead_minutes=30, _now=now)
        assert result == datetime.datetime(2026, 5, 5, 18, 0)

    def test_noon_start_picks_remaining_today_then_tomorrow(self):
        """Simulates the typical case: bot runs ~noon, 4 videos to schedule."""
        now = datetime.datetime(2026, 5, 5, 12, 0)
        s1 = next_publish_slot(now, SLOTS, min_lead_minutes=30, _now=now)
        s2 = next_publish_slot(s1, SLOTS, min_lead_minutes=30, _now=now)
        s3 = next_publish_slot(s2, SLOTS, min_lead_minutes=30, _now=now)
        s4 = next_publish_slot(s3, SLOTS, min_lead_minutes=30, _now=now)

        assert s1 == datetime.datetime(2026, 5, 5, 13, 0)
        assert s2 == datetime.datetime(2026, 5, 5, 18, 0)
        assert s3 == datetime.datetime(2026, 5, 5, 20, 0)
        assert s4 == datetime.datetime(2026, 5, 6, 11, 0)

    def test_empty_slots_raises(self):
        after = datetime.datetime(2026, 5, 5, 12, 0)
        with pytest.raises(ValueError):
            next_publish_slot(after, [], min_lead_minutes=30)
