"""Importing the publish log from before the history (FR-017)."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts import import_history
from src.entities.history import PublishAttempt, VideoRecord
from src.storage import SqliteHistoryStore

SAMPLE = Path(__file__).parents[1] / "fixtures" / "publish_log_sample.csv"
VIZINHA = "https://www.reddit.com/r/contos/comments/aaa/vizinha/"
CHEFE = "https://www.reddit.com/r/contos/comments/bbb/chefe/"
CASAMENTO = "https://www.reddit.com/r/contos/comments/ccc/casamento/"


@pytest.fixture
def history(tmp_path):
    return SqliteHistoryStore(str(tmp_path / "history.sqlite"))


@pytest.fixture
def manifests(tmp_path):
    """Today's manifests: story_01 was overwritten by the chefe story, and the
    mp4 of the casamento's part 2 is gone."""
    directory = tmp_path / "daily"
    directory.mkdir()
    (directory / "story_01.mp4").write_bytes(b"video")
    for name, manifest in {
        "story_01.json": {
            "video_path": "output/daily/story_01.mp4",
            "title": "O chefe, a planilha e eu",
            "summary": "Resumo do chefe",
            "post_url": CHEFE,
        },
        "story_02_p2.json": {
            "video_path": "output/daily/story_02_p2.mp4",
            "title": "O casamento - Parte 2",
            "summary": "Resumo do casamento",
            "post_url": CASAMENTO,
            "part": 2,
        },
    }.items():
        (directory / name).write_text(json.dumps(manifest), encoding="utf-8")
    return str(directory)


def test_every_row_becomes_an_attempt_under_its_video(history, manifests):
    result = import_history.import_publish_log(history, str(SAMPLE), [manifests])

    assert (result.records, result.attempts, result.existing) == (4, 5, 0)

    vizinha = history.find_record_by_video_path(
        "output/daily/story_01.mp4", post_url=VIZINHA
    )
    assert vizinha.imported and vizinha.run_id is None and vizinha.grade is None
    assert (vizinha.title, vizinha.part_index, vizinha.part_count) == (
        "A vizinha e o bolo",
        1,
        1,
    )
    # Today's manifest at that path is another story's: no summary borrowed.
    assert vizinha.summary == ""
    assert vizinha.created_at == datetime(2026, 5, 28, 19, 49, 21).astimezone()
    failed, scheduled = history.publish_attempts(vizinha.id)
    assert (failed.status, failed.error) == ("failed", "browser crashed")
    assert scheduled.status == "scheduled"
    assert scheduled.scheduled_at == datetime(2026, 5, 29, 12, 0).astimezone()
    assert scheduled.hashtags == ["fyp", "storytime", "reddit", "vizinha"]
    assert scheduled.publish_result.startswith("✅ Video scheduled")
    assert "\n- Schedule: May 29, 2026" in scheduled.publish_result


def test_the_path_reused_next_day_is_a_different_video(history, manifests):
    import_history.import_publish_log(history, str(SAMPLE), [manifests])

    chefe = history.find_record_by_video_path("output/daily/story_01.mp4")

    assert chefe.post_url == CHEFE
    assert chefe.summary == "Resumo do chefe"
    assert [a.status for a in history.publish_attempts(chefe.id)] == ["scheduled"]


def test_a_part_whose_mp4_is_gone_is_imported_with_its_part(history, manifests):
    import_history.import_publish_log(history, str(SAMPLE), [manifests])

    part = history.find_record_by_video_path("output/daily/story_02_p2.mp4")

    assert (part.part_index, part.part_count) == (2, 2)
    assert part.summary == "Resumo do casamento"


def test_test_rows_are_imported_too(history):
    import_history.import_publish_log(history, str(SAMPLE), [])

    stray = history.find_record_by_video_path(
        "/private/var/folders/sc/T/pytest-of-user/pytest-6/test_full_pipeline0/"
        "story_01.mp4"
    )
    assert [a.status for a in history.publish_attempts(stray.id)] == ["failed"]


def test_a_second_import_adds_nothing(history, manifests):
    import_history.import_publish_log(history, str(SAMPLE), [manifests])

    again = import_history.import_publish_log(history, str(SAMPLE), [manifests])

    assert str(again) == "0 registros criados, 0 tentativas, 5 já existiam"


def test_an_attempt_the_run_already_recorded_is_not_repeated(history):
    """The run logs the row, then records the attempt a moment later."""
    live = history.add_video_record(
        VideoRecord(
            created_at=datetime(2026, 5, 29, 19, 0),
            run_id=1,
            video_path="output/daily/story_01.mp4",
            title="O chefe, a planilha e eu",
            summary="",
            post_url=CHEFE,
        ),
        None,
    )
    history.add_publish_attempt(
        live,
        PublishAttempt(
            attempted_at=datetime(2026, 5, 29, 19, 30, 0, 400000),
            status="scheduled",
            scheduled_at=datetime(2026, 5, 30, 12, 0),
            hashtags=["fyp", "storytime"],
        ),
    )

    result = import_history.import_publish_log(history, str(SAMPLE), [])

    assert (result.records, result.attempts, result.existing) == (3, 4, 1)
    assert len(history.publish_attempts(live)) == 1


def test_the_command_line_prints_the_counts(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HISTORY_DB_PATH", str(tmp_path / "cli.sqlite"))

    assert import_history.main(["--csv", str(SAMPLE)]) == 0
    assert capsys.readouterr().out.strip() == (
        "4 registros criados, 5 tentativas, 0 já existiam"
    )


def test_a_missing_log_fails(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HISTORY_DB_PATH", str(tmp_path / "cli.sqlite"))

    assert import_history.main(["--csv", str(tmp_path / "nope.csv")]) == 1
    assert "nope.csv" in capsys.readouterr().err
