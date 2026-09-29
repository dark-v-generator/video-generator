"""What the performance history keeps about each video, run and collection.

Only results go in here: the numbers, the grade, the recipe and the outcomes.
The model's reasoning, rendered prompts, drafts and traces are process and stay
out, so the history can be read years later without knowing how the run worked.
"""

from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Literal, Optional

SkipReason = Literal["content_filter", "script", "render", "publish", "not_needed"]
RunMode = Literal["run", "generate", "publish"]
SnapshotSource = Literal["discovery", "collection"]
AttemptStatus = Literal["scheduled", "failed"]

# The traffic source TikTok's algorithm feeds, as the Studio names it.
FOR_YOU = "For You"

# The evaluate_story prompt's criterion keys, by the name the history uses.
_CRITERIA = {
    "retention": "retencao",
    "quality": "qualidade",
    "virality": "viralizacao",
    "tiktok_fit": "adequacao_tiktok",
    "hook": "gancho",
}


@dataclass(frozen=True)
class RedditSnapshot:
    """The post's public numbers at one moment; None when the post is gone."""

    taken_at: datetime
    source: SnapshotSource
    score: Optional[int]
    num_comments: Optional[int]
    upvote_ratio: Optional[float]
    available: bool = True


@dataclass(frozen=True)
class ModelGrade:
    """The model's grade of the story. The summary lives on the record."""

    overall: float
    verdict: str
    retention: Optional[float] = None
    quality: Optional[float] = None
    virality: Optional[float] = None
    tiktok_fit: Optional[float] = None
    hook: Optional[float] = None

    @classmethod
    def from_evaluation(cls, evaluation: dict) -> "ModelGrade":
        """The grade from the evaluate_story answer; a failed evaluation has
        no per-criterion grades, so those stay None."""
        grades = evaluation.get("notas") or {}
        return cls(
            overall=evaluation.get("nota_geral", 0.0),
            verdict=evaluation.get("veredito", ""),
            **{
                name: grades[key]["nota"] if key in grades else None
                for name, key in _CRITERIA.items()
            },
        )


@dataclass(frozen=True)
class ProductionRecipe:
    """How a video was made: prompt versions, models, voice and rendering."""

    story_prompt_version: str
    grading_prompt_version: str
    writer_model: str
    grader_model: str
    rendering_strategy: str
    speech_provider: str
    speech_rate: Optional[float]
    narrator_gender: str
    voice_id: str
    # None on videos made before the hashtags prompt was versioned.
    hashtags_prompt_version: Optional[str] = None

    @classmethod
    def empty(cls) -> "ProductionRecipe":
        return cls("", "", "", "", "", "", None, "", "")


@dataclass(frozen=True)
class PublishAttempt:
    """One call to the publisher, the same facts as its publish-log row."""

    attempted_at: datetime
    status: AttemptStatus
    scheduled_at: Optional[datetime]
    hashtags: list[str]
    publish_result: str = ""
    error: str = ""


@dataclass(frozen=True)
class PerformanceMetrics:
    """What TikTok counts for a video; None when the Studio does not show it."""

    views: Optional[int] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    saves: Optional[int] = None
    avg_watch_seconds: Optional[float] = None
    full_watch_ratio: Optional[float] = None
    new_followers: Optional[int] = None
    # The share of viewers still watching at each whole second, 1.0 at 0 s:
    # where the hook or the middle loses people.
    retention: Optional[tuple[float, ...]] = None
    # The share of views by where they came from ("For You", "Search", ...).
    traffic_sources: Optional[dict[str, float]] = None

    def retained_at(self, second: int) -> Optional[float]:
        """The share still watching at ``second``; None past the curve's end."""
        if self.retention is None or second >= len(self.retention):
            return None
        return self.retention[second]

    def traffic_share(self, source: str) -> Optional[float]:
        """The share of views from ``source``; None when the Studio gave no
        breakdown, 0 when it gave one without that source."""
        if self.traffic_sources is None:
            return None
        return self.traffic_sources.get(source, 0.0)


@dataclass(frozen=True)
class TikTokVideoStats:
    """A video as the Studio lists it, before it is matched to a record."""

    video_id: str
    description: str
    created_at: Optional[datetime]
    metrics: PerformanceMetrics


@dataclass(frozen=True)
class PerformanceSnapshot:
    taken_at: datetime
    tiktok_video_id: str
    metrics: PerformanceMetrics
    tiktok_created_at: Optional[datetime] = None


@dataclass(frozen=True)
class VideoRecord:
    """One rendered video. Parts of a story are sibling records."""

    created_at: datetime
    run_id: Optional[int]
    video_path: str
    title: str
    summary: str
    post_url: str
    community: str = ""
    author: str = ""
    post_created_utc: Optional[datetime] = None
    part_index: int = 1
    part_count: int = 1
    language: str = ""
    duration_seconds: Optional[float] = None
    grade: Optional[ModelGrade] = None
    deterministic_score: Optional[float] = None
    recipe: Optional[ProductionRecipe] = None
    hashtags: list[str] = field(default_factory=list)
    tiktok_video_id: Optional[str] = None
    imported: bool = False
    id: Optional[int] = None


@dataclass(frozen=True)
class PublishedRecord:
    """A record as a collection matches it: with the slot of its newest
    scheduled attempt, which is when TikTok made the video public."""

    record: VideoRecord
    scheduled_at: Optional[datetime]


@dataclass(frozen=True)
class RunSummary:
    """What a daily run did, whether or not it produced anything."""

    started_at: datetime
    finished_at: Optional[datetime]
    mode: RunMode
    requested: int
    target: int
    candidates_found: int
    produced: int
    scheduled: int
    skipped: dict[SkipReason, int]
    stopped_reason: str = ""
    id: Optional[int] = None


@dataclass(frozen=True)
class Collection:
    started_at: datetime
    finished_at: datetime
    lookback_days: int
    matched: int
    unmatched: int
    ambiguous: int
    reddit_refreshed: int


@dataclass(frozen=True)
class CollectionReport:
    collection: Collection
    unmatched_videos: list[TikTokVideoStats]
    # Each ambiguous video with the ids of the records it could belong to.
    ambiguous: list[tuple[TikTokVideoStats, list[int]]]


_RECORD_COLUMNS = (
    "id",
    "created_at",
    "run_id",
    "video_path",
    "title",
    "summary",
    "post_url",
    "community",
    "author",
    "post_created_utc",
    "part_index",
    "part_count",
    "language",
    "duration_seconds",
)
_GRADE_COLUMNS = ("overall", "verdict", *_CRITERIA)
_RECIPE_COLUMNS = tuple(f.name for f in fields(ProductionRecipe))
_REDDIT_COLUMNS = ("score", "num_comments", "upvote_ratio", "taken_at")
# The curve and the breakdown are not columns: the crossed view shows the
# points of them that compare across videos.
METRIC_COLUMNS = tuple(
    f.name
    for f in fields(PerformanceMetrics)
    if f.name not in ("retention", "traffic_sources")
)
RETAINED_AT_SECONDS = (3, 10)

# The crossed view's columns by name, in the order a table or CSV shows them;
# the names sorting and filtering accept.
CROSSED_COLUMNS: tuple[str, ...] = (
    *_RECORD_COLUMNS,
    *(f"grade_{name}" for name in _GRADE_COLUMNS),
    "deterministic_score",
    *_RECIPE_COLUMNS,
    "hashtags",
    "imported",
    "last_attempt_status",
    "last_scheduled_at",
    *(f"discovery_{name}" for name in _REDDIT_COLUMNS),
    *(f"latest_reddit_{name}" for name in _REDDIT_COLUMNS),
    "latest_reddit_available",
    "tiktok_video_id",
    *(f"latest_{name}" for name in METRIC_COLUMNS),
    *(f"latest_retained_{second}s" for second in RETAINED_AT_SECONDS),
    "latest_for_you_ratio",
    "latest_taken_at",
)


@dataclass(frozen=True)
class CrossedRow:
    """One video across the history: record, grade, recipe and latest numbers.

    ``latest_reddit`` is the newest snapshot a collection took, not the one
    from discovery: a video never collected has no "now" yet.
    """

    record: VideoRecord
    discovery: Optional[RedditSnapshot]
    latest_reddit: Optional[RedditSnapshot]
    latest_performance: Optional[PerformanceSnapshot]
    last_attempt: Optional[PublishAttempt]

    def columns(self) -> dict[str, object]:
        """The row flattened into CROSSED_COLUMNS; None where a part is missing."""
        record, grade, recipe = self.record, self.record.grade, self.record.recipe
        performance, attempt = self.latest_performance, self.last_attempt
        return {
            **{name: getattr(record, name) for name in _RECORD_COLUMNS},
            **{
                f"grade_{name}": getattr(grade, name) if grade else None
                for name in _GRADE_COLUMNS
            },
            "deterministic_score": record.deterministic_score,
            **{
                name: getattr(recipe, name) if recipe else None
                for name in _RECIPE_COLUMNS
            },
            "hashtags": " ".join(f"#{tag}" for tag in record.hashtags),
            "imported": record.imported,
            "last_attempt_status": attempt.status if attempt else None,
            "last_scheduled_at": attempt.scheduled_at if attempt else None,
            **_snapshot_columns("discovery", self.discovery),
            **_snapshot_columns("latest_reddit", self.latest_reddit),
            "latest_reddit_available": (
                self.latest_reddit.available if self.latest_reddit else None
            ),
            "tiktok_video_id": record.tiktok_video_id,
            **{
                f"latest_{name}": (
                    getattr(performance.metrics, name) if performance else None
                )
                for name in METRIC_COLUMNS
            },
            **{
                f"latest_retained_{second}s": (
                    performance.metrics.retained_at(second) if performance else None
                )
                for second in RETAINED_AT_SECONDS
            },
            "latest_for_you_ratio": (
                performance.metrics.traffic_share(FOR_YOU) if performance else None
            ),
            "latest_taken_at": performance.taken_at if performance else None,
        }


def _snapshot_columns(
    prefix: str, snapshot: Optional[RedditSnapshot]
) -> dict[str, object]:
    return {
        f"{prefix}_{name}": getattr(snapshot, name) if snapshot else None
        for name in _REDDIT_COLUMNS
    }
