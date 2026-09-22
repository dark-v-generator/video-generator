"""Tests for the on-server queue of locally prepared story packages."""

import json
import os
import time

import pytest

from src.entities.prepared_story import PreparedStoryPackage, TwoPartStoryPackage
from src.services.prepared_story_queue import PreparedStoryQueue

from tests.test_prepared_story_package import (
    POST_URL,
    package_payload,
    two_part_payload,
)


def other_post_url(post_id: str) -> str:
    return f"https://www.reddit.com/r/test/comments/{post_id}/slug/"


def write_inbox(root, post_id: str, **overrides) -> str:
    """Drop a valid package in inbox/ and return its path."""
    return _write(root, post_id, package_payload(**overrides))


def write_two_part_inbox(root, post_id: str, **overrides) -> str:
    """Drop a valid two-part package in inbox/ and return its path."""
    return _write(root, post_id, two_part_payload(**overrides))


def _write(root, post_id: str, payload: dict) -> str:
    payload["post"] = {**payload["post"], "url": other_post_url(post_id)}
    path = os.path.join(root, "inbox", f"{post_id}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


class TestDirectories:
    def test_creates_the_three_state_directories_on_demand(self, tmp_path):
        root = tmp_path / "prepared"

        queue = PreparedStoryQueue(str(root))
        assert queue.list_inbox() == []

        for name in ("inbox", "done", "failed"):
            assert (root / name).is_dir()


class TestListInbox:
    def test_empty_inbox_is_an_empty_list(self, tmp_path):
        queue = PreparedStoryQueue(str(tmp_path))

        assert queue.list_inbox() == []

    def test_orders_by_mtime_then_name(self, tmp_path):
        write_inbox(str(tmp_path), "bbb")
        write_inbox(str(tmp_path), "aaa")
        write_inbox(str(tmp_path), "ccc")

        # Same mtime for aaa and bbb, a later one for ccc: name breaks the tie
        # inside the older pair, and ccc still comes last.
        shared = time.time() - 60
        for name in ("aaa.json", "bbb.json"):
            path = tmp_path / "inbox" / name
            os.utime(path, (shared, shared))

        queue = PreparedStoryQueue(str(tmp_path))
        ids = [item.package.post_id for item in queue.list_inbox()]

        assert ids == ["aaa", "bbb", "ccc"]

    def test_ignores_files_that_are_not_json(self, tmp_path):
        write_inbox(str(tmp_path), "aaa")
        (tmp_path / "inbox" / "notes.txt").write_text("ignore me")

        queue = PreparedStoryQueue(str(tmp_path))

        assert [item.package.post_id for item in queue.list_inbox()] == ["aaa"]

    def test_unparseable_package_is_moved_to_failed_and_left_out(self, tmp_path):
        write_inbox(str(tmp_path), "good")
        broken = tmp_path / "inbox" / "broken.json"
        broken.write_text("{not json at all")

        queue = PreparedStoryQueue(str(tmp_path))
        items = queue.list_inbox()

        assert [item.package.post_id for item in items] == ["good"]
        assert not broken.exists()
        assert (tmp_path / "failed" / "broken.json").exists()
        error = (tmp_path / "failed" / "broken.error.txt").read_text()
        assert "broken.json" in error

    def test_package_with_unknown_version_is_moved_to_failed(self, tmp_path):
        write_inbox(str(tmp_path), "old", version=2)

        queue = PreparedStoryQueue(str(tmp_path))

        assert queue.list_inbox() == []
        assert (tmp_path / "failed" / "old.json").exists()
        assert (tmp_path / "failed" / "old.error.txt").exists()

    def test_item_carries_path_package_and_mtime(self, tmp_path):
        path = write_inbox(str(tmp_path), "aaa")

        (item,) = PreparedStoryQueue(str(tmp_path)).list_inbox()

        assert item.path == path
        assert isinstance(item.package, PreparedStoryPackage)
        assert item.mtime == pytest.approx(os.path.getmtime(path))


class TestMarkDone:
    def test_moves_the_package_and_writes_the_outcome(self, tmp_path):
        write_inbox(str(tmp_path), "aaa")
        queue = PreparedStoryQueue(str(tmp_path))
        (item,) = queue.list_inbox()

        queue.mark_done(
            item,
            {
                "status": "scheduled",
                "scheduled_at": "2026-09-23T18:00",
                "hashtags": ["fyp"],
                "video_path": "output/daily/story_01.mp4",
                "manifest_path": "output/daily/story_01.json",
            },
        )

        assert not (tmp_path / "inbox" / "aaa.json").exists()
        assert (tmp_path / "done" / "aaa.json").exists()

        outcome = json.loads((tmp_path / "done" / "aaa.outcome.json").read_text())
        assert outcome == {
            "status": "scheduled",
            "scheduled_at": "2026-09-23T18:00",
            "hashtags": ["fyp"],
            "video_path": "output/daily/story_01.mp4",
            "manifest_path": "output/daily/story_01.json",
        }

    def test_generate_only_outcome_has_no_schedule(self, tmp_path):
        write_inbox(str(tmp_path), "aaa")
        queue = PreparedStoryQueue(str(tmp_path))
        (item,) = queue.list_inbox()

        queue.mark_done(
            item,
            {
                "status": "generated",
                "scheduled_at": None,
                "hashtags": None,
                "video_path": "output/daily/story_01.mp4",
                "manifest_path": "output/daily/story_01.json",
            },
        )

        outcome = json.loads((tmp_path / "done" / "aaa.outcome.json").read_text())
        assert outcome["status"] == "generated"
        assert outcome["scheduled_at"] is None


class TestMarkFailed:
    def test_moves_the_package_and_writes_the_error(self, tmp_path):
        write_inbox(str(tmp_path), "aaa")
        queue = PreparedStoryQueue(str(tmp_path))
        (item,) = queue.list_inbox()

        queue.mark_failed(item, "language: package=en server=pt")

        assert not (tmp_path / "inbox" / "aaa.json").exists()
        assert (tmp_path / "failed" / "aaa.json").exists()
        assert (
            tmp_path / "failed" / "aaa.error.txt"
        ).read_text() == "language: package=en server=pt"


class TestKnownPostUrls:
    def test_is_the_union_of_inbox_and_done(self, tmp_path):
        write_inbox(str(tmp_path), "aaa")
        write_inbox(str(tmp_path), "bbb")
        queue = PreparedStoryQueue(str(tmp_path))
        done = next(i for i in queue.list_inbox() if i.package.post_id == "bbb")
        queue.mark_done(done, {"status": "generated"})

        assert queue.known_post_urls() == {
            other_post_url("aaa"),
            other_post_url("bbb"),
        }

    def test_failed_packages_are_not_known(self, tmp_path):
        write_inbox(str(tmp_path), "aaa")
        queue = PreparedStoryQueue(str(tmp_path))
        (item,) = queue.list_inbox()
        queue.mark_failed(item, "boom")

        assert queue.known_post_urls() == set()

    def test_empty_queue_has_no_known_urls(self, tmp_path):
        assert PreparedStoryQueue(str(tmp_path)).known_post_urls() == set()


class TestTwoPartPackages:
    def test_version_two_is_listed_with_its_own_model(self, tmp_path):
        write_two_part_inbox(str(tmp_path), "aaa")

        (item,) = PreparedStoryQueue(str(tmp_path)).list_inbox()

        assert isinstance(item.package, TwoPartStoryPackage)
        assert item.package.post_id == "aaa"

    def test_unsupported_version_goes_to_failed_with_a_stable_message(self, tmp_path):
        payload = two_part_payload(version=7)
        payload["post"] = {**payload["post"], "url": other_post_url("aaa")}
        os.makedirs(tmp_path / "inbox")
        (tmp_path / "inbox" / "aaa.json").write_text(json.dumps(payload))

        queue = PreparedStoryQueue(str(tmp_path))

        assert queue.list_inbox() == []
        assert (tmp_path / "failed" / "aaa.json").exists()
        error = (tmp_path / "failed" / "aaa.error.txt").read_text()
        assert "unsupported package version" in error
        assert queue.last_rejections[0][0] == "aaa.json"

    def test_known_post_urls_covers_both_versions(self, tmp_path):
        write_inbox(str(tmp_path), "aaa")
        write_two_part_inbox(str(tmp_path), "bbb")

        urls = PreparedStoryQueue(str(tmp_path)).known_post_urls()

        assert urls == {other_post_url("aaa"), other_post_url("bbb")}
