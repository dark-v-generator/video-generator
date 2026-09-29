"""Rows, videos and cycles for the tuning arithmetic, built with only the
fields it reads."""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from src.capabilities.tuning import Video
from src.entities.history import (
    CrossedRow,
    PerformanceMetrics,
    PerformanceSnapshot,
    ProductionRecipe,
    PublishAttempt,
    VideoRecord,
)
from src.entities.tuning import Cycle, PromptVersions, Settings

# Mid-day UTC, so the local date is the same in any timezone near Brazil.
T0 = datetime(2026, 9, 1, 15, 0, tzinfo=timezone.utc)
DAY0 = date(2026, 9, 1)


def at(days: float) -> datetime:
    return T0 + timedelta(days=days)


def recipe(writer: str = "kimi", grader: str = "deepseek") -> ProductionRecipe:
    return ProductionRecipe(
        "s" * 12, "g" * 12, writer, grader, "narration", "edge-tts", 1.2, "male", "v"
    )


def row(
    record_id: int,
    *,
    created: Optional[datetime] = None,
    views: Optional[int] = None,
    taken: Optional[datetime] = None,
    tiktok_created: Optional[datetime] = None,
    recipe: Optional[ProductionRecipe] = None,
) -> CrossedRow:
    """A record, with a TikTok snapshot when ``taken`` is given."""
    performance = (
        PerformanceSnapshot(
            taken_at=taken,
            tiktok_video_id=f"v{record_id}",
            metrics=PerformanceMetrics(views=views),
            tiktok_created_at=tiktok_created,
        )
        if taken
        else None
    )
    return CrossedRow(
        record=VideoRecord(
            created_at=created or T0,
            run_id=1,
            video_path=f"v{record_id}.mp4",
            title=f"t{record_id}",
            summary="",
            post_url="",
            recipe=recipe,
            id=record_id,
        ),
        discovery=None,
        latest_reddit=None,
        latest_performance=performance,
        last_attempt=None,
    )


def scheduled(slot: datetime) -> PublishAttempt:
    return PublishAttempt(
        attempted_at=slot - timedelta(hours=3),
        status="scheduled",
        scheduled_at=slot,
        hashtags=[],
    )


def failed(when: datetime) -> PublishAttempt:
    return PublishAttempt(
        attempted_at=when, status="failed", scheduled_at=None, hashtags=[]
    )


def video(
    record_id: int,
    *,
    day: float = 0,
    views: Optional[int] = 100,
    settled: bool = True,
    relative: Optional[float] = 1.0,
    goal: Optional[str] = None,
    cycle: Optional[int] = None,
    recipe: Optional[ProductionRecipe] = None,
) -> Video:
    """A measured video published and created on ``day``."""
    return Video(
        row=row(
            record_id,
            created=at(day),
            views=views,
            taken=at(day + 10) if views is not None else None,
            recipe=recipe,
        ),
        published_at=at(day),
        settled=settled,
        relative=relative if settled else None,
        neighbours=10 if settled and relative is not None else 0,
        goal=goal,
        cycle=cycle,
    )


def cycle(
    number: int,
    *,
    deployed: Optional[date] = None,
    closed: Optional[date] = None,
    writer: str = "kimi",
    story: str = "a" * 12,
) -> Cycle:
    return Cycle(
        number=number,
        opened=deployed or DAY0,
        deployed=deployed,
        closed=closed,
        prompts=PromptVersions(
            story=story, evaluate_story="b" * 12, generate_hashtags="c" * 12
        ),
        settings=Settings(
            writer_model=writer, grader_model="deepseek", rendering_strategy="narration"
        ),
    )
