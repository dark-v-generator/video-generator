"""What a daily run leaves behind: the manifests and publish log the next run
reads, and the history the analysis reads.

The run tells its record what happened, as it happens; the record keeps the
counts and turns the run's objects into history entries, so the flow stays
about decisions. Manifest before history, publish-log row before attempt: a
history write that fails leaves the files as they always were and stops the run.
"""

import dataclasses
import functools
import inspect
from datetime import datetime, timezone
from typing import Callable, Optional, get_args

from ..entities.generated_video import GeneratedVideo
from ..entities.history import (
    ModelGrade,
    ProductionRecipe,
    PublishAttempt,
    RedditSnapshot,
    RunMode,
    RunSummary,
    SkipReason,
    VideoRecord,
)
from ..entities.story import Story
from ..entities.story_candidate import EvaluatedStory
from ..storage import HistoryError, HistoryStore, PublishLogEntry, RunStore

# Skips that end a candidate before it becomes a video.
_BEFORE_VIDEO: tuple[SkipReason, ...] = ("content_filter", "script", "render")


@dataclasses.dataclass(kw_only=True)
class RunRecord:
    store: RunStore
    history: HistoryStore
    recipe: ProductionRecipe
    mode: RunMode
    requested: int
    now: Callable[[], datetime]
    target: int = 0
    candidates_found: int = 0
    stopped_reason: str = ""
    produced: int = 0
    scheduled: int = 0
    skipped: dict[SkipReason, int] = dataclasses.field(
        default_factory=lambda: dict.fromkeys(get_args(SkipReason), 0)
    )

    def __post_init__(self) -> None:
        self.started_at = self.now()
        self.run_id = self.history.start_run(
            mode=self.mode, requested=self.requested, started_at=self.started_at
        )
        self._record_ids: dict[str, int] = {}
        self._stories: set[str] = set()

    def found(self, candidates: int, target: int) -> None:
        self.candidates_found, self.target = candidates, target
        if not candidates:
            self.stopped_reason = "no_candidates"

    def stop(self, reason: str) -> None:
        self.stopped_reason = reason

    def skip(self, reason: SkipReason) -> None:
        self.skipped[reason] += 1

    def publish_failed(self, error: Exception) -> None:
        """Count a video the publisher did not take. A history write that
        failed is not a publish failure: it stops the run."""
        if isinstance(error, HistoryError):
            raise error
        self.skip("publish")

    def video(
        self,
        video: GeneratedVideo,
        candidate: EvaluatedStory,
        story: Story,
        output_dir: str,
    ) -> None:
        """Save the video's manifest, then its record with the post's numbers."""
        self.store.save_manifest(video, output_dir)
        post = candidate.post
        now = self.now()
        record = VideoRecord(
            created_at=now,
            run_id=self.run_id,
            video_path=video.video_path,
            title=video.title,
            summary=video.summary,
            post_url=video.post_url,
            community=post.community,
            author=post.author,
            post_created_utc=(
                datetime.fromtimestamp(post.created_utc, timezone.utc)
                if post.created_utc is not None
                else None
            ),
            part_index=video.part or 1,
            part_count=len(story.parts),
            language=story.language.value,
            grade=ModelGrade.from_evaluation(candidate.evaluation),
            deterministic_score=candidate.deterministic_score,
            recipe=self.recipe,
        )
        signals = RedditSnapshot(
            taken_at=now,
            source="discovery",
            score=post.score,
            num_comments=post.num_comments,
            upvote_ratio=post.upvote_ratio,
        )
        self._record_ids[video.video_path] = self.history.add_video_record(
            record, signals
        )
        self._stories.add(video.post_url)
        self.produced += 1

    def publish_log(self, entry: PublishLogEntry) -> None:
        """Log one publish outcome, then add it to the video's attempts."""
        self.store.append_publish_log(entry)
        self.history.add_publish_attempt(
            self._record_id(entry.video),
            PublishAttempt(
                attempted_at=self.now(),
                status=entry.status,
                scheduled_at=entry.scheduled_at,
                hashtags=list(entry.hashtags),
                publish_result=entry.publish_result,
                error=entry.error,
            ),
        )
        if entry.status == "scheduled":
            self.scheduled += 1

    def _record_id(self, video: GeneratedVideo) -> int:
        """The video's record: made by this run, found by path, or, for a video
        rendered before the history existed, a minimal one from its manifest."""
        if video.video_path in self._record_ids:
            return self._record_ids[video.video_path]
        found = self.history.find_record_by_video_path(video.video_path)
        if found is not None:
            return found.id
        part = video.part or 1
        minimal = VideoRecord(
            created_at=self.now(),
            run_id=self.run_id,
            video_path=video.video_path,
            title=video.title,
            summary=video.summary,
            post_url=video.post_url,
            # The manifest knows the part, not how many there were.
            part_index=part,
            part_count=part,
            imported=True,
        )
        return self.history.add_video_record(minimal, None)

    def finish(self) -> None:
        # Candidates never tried were not needed: the target was met first.
        tried = len(self._stories) + sum(self.skipped[r] for r in _BEFORE_VIDEO)
        self.skipped["not_needed"] = self.candidates_found - tried
        self.history.finish_run(
            self.run_id,
            RunSummary(
                started_at=self.started_at,
                finished_at=self.now(),
                mode=self.mode,
                requested=self.requested,
                target=self.target,
                candidates_found=self.candidates_found,
                produced=self.produced,
                scheduled=self.scheduled,
                skipped=dict(self.skipped),
                stopped_reason=self.stopped_reason,
            ),
        )


def recorded(mode: RunMode):
    """Give the decorated run a fresh ``flow.record`` and finish it on return.

    A run that raises leaves its summary unfinished, which is how the history
    tells a run that died from one that found nothing.
    """

    def decorate(method):
        signature = inspect.signature(method)

        @functools.wraps(method)
        async def wrapper(flow, *args, **kwargs):
            call = signature.bind(flow, *args, **kwargs).arguments
            videos: Optional[list] = call.get("videos")
            count = call.get("count")
            flow.record = RunRecord(
                store=flow.store,
                history=flow.history,
                recipe=flow.recipe,
                mode=mode,
                requested=(
                    len(videos)
                    if videos is not None
                    else count if count is not None else flow.config.count
                ),
                now=flow.now,
            )
            if videos is not None:
                flow.record.target = len(videos)
            result = await method(flow, *args, **kwargs)
            flow.record.finish()
            return result

        return wrapper

    return decorate
