"""The crossed view from the command line (US3, SC-003)."""

import csv
from datetime import datetime, timedelta, timezone

import pytest

from scripts import performance_report
from src.entities.history import (
    CROSSED_COLUMNS,
    Collection,
    ModelGrade,
    PerformanceMetrics,
    PerformanceSnapshot,
    ProductionRecipe,
    PublishAttempt,
    RedditSnapshot,
    VideoRecord,
)
from src.storage import SqliteHistoryStore

T0 = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)
COLLECTED = T0 + timedelta(days=5)


@pytest.fixture
def history(tmp_path, monkeypatch):
    path = tmp_path / "history.sqlite"
    monkeypatch.setenv("HISTORY_DB_PATH", str(path))
    return SqliteHistoryStore(str(path))


def seed(history, title, grade, views=None, *, days=0, prompt="abc123def456"):
    record_id = history.add_video_record(
        VideoRecord(
            created_at=T0 + timedelta(days=days),
            run_id=1,
            video_path=f"output/daily/{title}.mp4",
            title=title,
            summary="",
            post_url=f"https://reddit.com/r/contos/comments/{title}/",
            grade=ModelGrade(overall=grade, verdict="Boa"),
            recipe=ProductionRecipe(
                prompt, "g", "anthropic/claude", "m", "s", "edge-tts", 1.2, "male", "v"
            ),
        ),
        RedditSnapshot(
            taken_at=T0,
            source="discovery",
            score=300,
            num_comments=20,
            upvote_ratio=0.9,
        ),
    )
    history.add_publish_attempt(
        record_id,
        PublishAttempt(
            attempted_at=T0 + timedelta(days=days),
            status="scheduled",
            scheduled_at=T0 + timedelta(days=days, hours=3),
            hashtags=["fyp"],
        ),
    )
    if views is not None:
        history.record_collection(
            Collection(COLLECTED, COLLECTED, 30, 1, 0, 0, 1),
            {
                record_id: PerformanceSnapshot(
                    taken_at=COLLECTED,
                    tiktok_video_id=f"v-{title}",
                    metrics=PerformanceMetrics(
                        views=views,
                        likes=10,
                        avg_watch_seconds=21.5,
                        full_watch_ratio=0.12,
                    ),
                )
            },
            {},
        )
    return record_id


@pytest.fixture
def seeded(history):
    return {
        "flopped": seed(history, "flopped", 92, views=150),
        "fine": seed(history, "fine", 88, views=40000),
        "took_off": seed(history, "took_off", 45, views=90000),
        "waiting": seed(history, "waiting", 70, days=2, prompt="fff000fff000"),
    }


def table(capsys) -> list[str]:
    lines = capsys.readouterr().out.splitlines()
    return lines[: lines.index("")]


def cell(lines: list[str], header: str, title: str) -> str:
    """The text under a right-aligned header in the row of *title*."""
    end = lines[0].index(header) + len(header)
    row = next(line for line in lines if f" {title} " in line)
    return row[:end].split("  ")[-1].strip()


def test_sorted_by_grade_the_high_grades_that_flopped_are_on_top(seeded, capsys):
    assert performance_report.main(["--sort", "grade_overall:desc"]) == 0

    lines = table(capsys)
    assert [line.split()[0] for line in lines[1:]] == [
        str(seeded[k]) for k in ("flopped", "fine", "waiting", "took_off")
    ]
    assert cell(lines, "views", "flopped") == "150"
    assert cell(lines, "nota", "flopped") == "92"
    assert cell(lines, "watch", "flopped") == "21.5s"
    assert cell(lines, "% fim", "flopped") == "12.0%"


def test_sorted_by_views_the_least_watched_come_first(seeded, capsys):
    assert performance_report.main(["--sort", "latest_views"]) == 0

    lines = table(capsys)
    assert [line.split()[0] for line in lines[1:]] == [
        str(seeded[k]) for k in ("flopped", "fine", "took_off", "waiting")
    ]


def test_a_video_not_collected_yet_is_there_with_empty_numbers(seeded, capsys):
    assert performance_report.main([]) == 0

    out = capsys.readouterr().out
    lines = out.splitlines()[:5]
    assert cell(lines, "views", "waiting") == ""
    assert cell(lines, "up desc.", "waiting") == "300"
    assert cell(lines, "up agora", "waiting") == ""
    assert out.endswith("\n\n4 vídeos\n")


def test_filter_and_since_narrow_the_rows(seeded, capsys):
    assert (
        performance_report.main(["--filter", "story_prompt_version=fff000fff000"]) == 0
    )
    assert [line.split()[0] for line in table(capsys)[1:]] == [str(seeded["waiting"])]

    assert performance_report.main(["--since", "2026-09-11"]) == 0
    assert [line.split()[0] for line in table(capsys)[1:]] == [str(seeded["waiting"])]


def test_the_csv_has_the_same_rows_with_every_column(seeded, tmp_path, capsys):
    out = tmp_path / "cross.csv"

    assert (
        performance_report.main(["--sort", "grade_overall:desc", "--csv", str(out)])
        == 0
    )

    assert capsys.readouterr().out.strip() == f"4 vídeos gravados em {out}"
    with open(out, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert tuple(rows[0]) == CROSSED_COLUMNS
    assert [int(row["id"]) for row in rows] == [
        seeded[k] for k in ("flopped", "fine", "waiting", "took_off")
    ]
    flopped, waiting = rows[0], rows[2]
    assert (flopped["latest_views"], flopped["tiktok_video_id"]) == ("150", "v-flopped")
    assert flopped["hashtags"] == "#fyp" and flopped["imported"] == "0"
    assert flopped["created_at"] == T0.isoformat()
    assert waiting["latest_views"] == "" and waiting["latest_taken_at"] == ""


def test_columns_lists_what_sort_and_filter_accept(capsys):
    assert performance_report.main(["--columns"]) == 0

    assert tuple(capsys.readouterr().out.split()) == CROSSED_COLUMNS


@pytest.mark.parametrize("args", [["--sort", "views:desc"], ["--filter", "prompt=abc"]])
def test_an_unknown_column_exits_2_listing_the_valid_ones(seeded, capsys, args):
    assert performance_report.main(args) == 2

    err = capsys.readouterr().err
    assert "Valid columns:" in err and "latest_views" in err


def test_a_malformed_sort_or_filter_is_a_usage_error(capsys):
    for args in (["--sort", "grade_overall:up"], ["--filter", "grade_overall"]):
        with pytest.raises(SystemExit) as exit:
            performance_report.main(args)
        assert exit.value.code == 2
