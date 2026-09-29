"""Every prompt version in the recipe reaches the crossed view."""

import dataclasses
from datetime import datetime, timezone

from src.entities.history import (
    CROSSED_COLUMNS,
    CrossedRow,
    ProductionRecipe,
    VideoRecord,
)


def test_the_hashtags_prompt_version_is_a_crossed_column():
    assert "hashtags_prompt_version" in CROSSED_COLUMNS


def test_the_crossed_row_carries_the_hashtags_prompt_version():
    recipe = dataclasses.replace(
        ProductionRecipe.empty(), hashtags_prompt_version="abc"
    )
    record = VideoRecord(
        created_at=datetime(2026, 9, 29, tzinfo=timezone.utc),
        run_id=1,
        video_path="out/a.mp4",
        title="t",
        summary="",
        post_url="u",
        recipe=recipe,
    )

    columns = CrossedRow(record, None, None, None, None).columns()

    assert columns["hashtags_prompt_version"] == "abc"
    assert list(columns) == list(CROSSED_COLUMNS)
