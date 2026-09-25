"""The file store writes and reads exactly what the bot wrote before the refactor."""

import csv
import datetime
import json
import os

from src.entities.generated_video import GeneratedVideo
from src.storage import FileRunStore, PublishLogEntry

HEADER = (
    "created_at,status,scheduled_at,video_path,title,post_url,hashtags,"
    "publish_result,error"
)


def _video(directory, name="story_01", **fields) -> GeneratedVideo:
    return GeneratedVideo(
        video_path=os.path.join(directory, f"{name}.mp4"),
        title=fields.pop("title", "Título"),
        summary=fields.pop("summary", "Resumo"),
        post_url=fields.pop("post_url", "https://reddit.com/p1"),
        **fields,
    )


def write_manifest(directory, name: str, **fields) -> None:
    mp4 = os.path.join(directory, f"{name}.mp4")
    with open(mp4, "wb") as f:
        f.write(b"video")
    with open(os.path.join(directory, f"{name}.json"), "w") as f:
        json.dump({"video_path": mp4, "summary": "s", **fields}, f)


class TestManifests:
    def test_one_part_manifest_has_no_part_key(self, tmp_path):
        store = FileRunStore(str(tmp_path / "log.csv"))

        path = store.save_manifest(_video(tmp_path, title="Olá"), str(tmp_path))

        assert path == str(tmp_path / "story_01.json")
        with open(path) as f:
            text = f.read()
        assert json.loads(text) == {
            "video_path": str(tmp_path / "story_01.mp4"),
            "title": "Olá",
            "summary": "Resumo",
            "post_url": "https://reddit.com/p1",
            "source": "auto",
        }
        assert '"title": "Olá"' in text  # ensure_ascii=False
        assert text.startswith('{\n  "video_path"')  # indent=2

    def test_a_part_is_written_and_read_back(self, tmp_path):
        store = FileRunStore(str(tmp_path / "log.csv"))
        video = _video(tmp_path, name="story_01_p2", part=2)
        (tmp_path / "story_01_p2.mp4").write_bytes(b"v")

        store.save_manifest(video, str(tmp_path))

        assert json.loads((tmp_path / "story_01_p2.json").read_text())["part"] == 2
        assert store.load_manifests(str(tmp_path)) == [video]

    def test_manifest_without_source_or_part_still_loads(self, tmp_path):
        write_manifest(tmp_path, "story_01", title="Old manifest", post_url="url")

        (video,) = FileRunStore("unused").load_manifests(str(tmp_path))

        assert video.title == "Old manifest"
        assert video.source == "auto"
        assert video.part is None

    def test_manifest_with_source_keeps_it(self, tmp_path):
        write_manifest(tmp_path, "story_01", title="New", post_url="url", source="x")

        (video,) = FileRunStore("unused").load_manifests(str(tmp_path))

        assert video.source == "x"

    def test_relative_video_path_resolves_inside_the_directory(self, tmp_path):
        (tmp_path / "story_01.mp4").write_bytes(b"v")
        (tmp_path / "story_01.json").write_text(
            json.dumps({"video_path": "elsewhere/story_01.mp4", "title": "T"})
        )

        (video,) = FileRunStore("unused").load_manifests(str(tmp_path))

        assert video.video_path == str(tmp_path / "story_01.mp4")

    def test_manifest_whose_video_is_gone_is_skipped(self, tmp_path):
        write_manifest(tmp_path, "story_01", title="Gone", post_url="url")
        os.remove(tmp_path / "story_01.mp4")

        assert FileRunStore("unused").load_manifests(str(tmp_path)) == []

    def test_manifests_load_in_file_name_order(self, tmp_path):
        for name in ("story_02", "story_01_p2", "story_01"):
            write_manifest(tmp_path, name, title=name, post_url="url")

        titles = [v.title for v in FileRunStore("unused").load_manifests(str(tmp_path))]

        assert titles == ["story_01", "story_01_p2", "story_02"]


class TestPublishLog:
    def test_header_once_and_columns_in_order(self, tmp_path):
        path = tmp_path / "nested" / "log.csv"
        store = FileRunStore(str(path))
        video = _video(tmp_path)
        slot = datetime.datetime(2026, 9, 25, 18, 0)

        store.append_publish_log(
            PublishLogEntry("scheduled", slot, video, ["fyp", "reddit"], "ok")
        )
        store.append_publish_log(
            PublishLogEntry("failed", None, video, [], error="boom")
        )

        lines = path.read_text().splitlines()
        assert lines[0] == HEADER
        assert len(lines) == 3
        first, second = list(csv.DictReader(lines))
        assert datetime.datetime.fromisoformat(first["created_at"])
        assert {k: v for k, v in first.items() if k != "created_at"} == {
            "status": "scheduled",
            "scheduled_at": "2026-09-25T18:00",
            "video_path": video.video_path,
            "title": "Título",
            "post_url": "https://reddit.com/p1",
            "hashtags": "#fyp #reddit",
            "publish_result": "ok",
            "error": "",
        }
        assert (second["status"], second["scheduled_at"], second["error"]) == (
            "failed",
            "",
            "boom",
        )

    def test_a_log_that_cannot_be_written_does_not_raise(self, tmp_path):
        (tmp_path / "file").write_text("")
        store = FileRunStore(str(tmp_path / "file" / "log.csv"))

        store.append_publish_log(
            PublishLogEntry("failed", None, _video(tmp_path), [], error="x")
        )


class TestScheduledPostUrls:
    def test_only_scheduled_rows_count(self, tmp_path):
        path = tmp_path / "log.csv"
        path.write_text(
            HEADER + "\n"
            "2026-09-20T10:00:00,scheduled,2026-09-20T18:00,a.mp4,A,url-a,,ok,\n"
            "2026-09-20T11:00:00,failed,,b.mp4,B,url-b,,,boom\n"
            "2026-09-20T12:00:00,scheduled,2026-09-20T19:00,c.mp4,C,url-c,,ok,\n"
        )

        assert FileRunStore(str(path)).scheduled_post_urls() == {"url-a", "url-c"}

    def test_missing_file_is_an_empty_set(self, tmp_path):
        assert FileRunStore(str(tmp_path / "nope.csv")).scheduled_post_urls() == set()

    def test_rows_without_a_post_url_are_skipped(self, tmp_path):
        path = tmp_path / "log.csv"
        path.write_text(
            HEADER + "\n"
            "2026-09-20T10:00:00,scheduled,2026-09-20T18:00,a.mp4,A,,,ok,\n"
        )

        assert FileRunStore(str(path)).scheduled_post_urls() == set()

    def test_what_the_store_logs_is_what_it_excludes(self, tmp_path):
        store = FileRunStore(str(tmp_path / "log.csv"))
        video = _video(tmp_path, post_url="url-z")

        store.append_publish_log(PublishLogEntry("scheduled", None, video, []))

        assert store.scheduled_post_urls() == {"url-z"}
