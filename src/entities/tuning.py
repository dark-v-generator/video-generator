"""The channel's tuning records: what it believes about its audience, what it
is testing, the prompt cycles and the reports that read the history.

The records are files the operator reads and the assistant writes; these
models only say what a valid record is. Rules about a single record are
enforced here, on load. Rules that tie records together (a challenge names a
belief that exists, a report is listed by its cycle) belong to the tuning
check, which sees all of them at once.
"""

from datetime import date, datetime
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Fewer videos than this and a pattern is a lead to test, never part of the
# base nor proof that something does not work.
EVIDENCE_MINIMUM = 10

# The editorial prompts a cycle versions, by the template each one is.
PROMPT_FILES = {
    "story": "story.jinja2",
    "evaluate_story": "evaluate_story.jinja2",
    "generate_hashtags": "generate_hashtags.jinja2",
    "evaluate_exploration": "evaluate_exploration.jinja2",
}

PromptName = Literal[
    "story", "evaluate_story", "generate_hashtags", "evaluate_exploration"
]
Area = Literal["story_kind", "title_opening", "posting", "other"]
Confidence = Literal["low", "medium", "high"]
Action = Literal["keep", "close"]
Fingerprint = Annotated[str, Field(pattern=r"^[0-9a-f]{12}$")]


class _Record(BaseModel):
    # A misspelt key is an error, not a field silently left at its default.
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Stamp(_Record):
    """When something started: the cycle in effect and the day."""

    cycle: int = Field(ge=1)
    date: date


class Period(_Record):
    since: date
    until: date

    @model_validator(mode="after")
    def _ordered(self) -> "Period":
        if self.since > self.until:
            raise ValueError(f"period starts {self.since}, after it ends {self.until}")
        return self


# ---------------------------------------------------------------- experiments


class Outcome(_Record):
    verdict: Literal[
        "confirmed",
        "refuted",
        "inconclusive",
        "closed_without_verdict",
        "not_testable",
    ]
    date: date
    cycle: int = Field(ge=1)
    videos: list[int] = []
    settled_count: int = Field(ge=0)
    median_relative: Optional[float] = None
    note: str = ""


class Experiment(_Record):
    """A question put to the audience with a slice of the production.

    Its place in the plan's list is its priority. An open experiment is never
    edited: changing it is closing it and opening another that ``replaces`` it,
    so the videos made for one question are never counted for another.
    """

    id: str = Field(pattern=r"^E\d{3}$")
    status: Literal["open", "closed", "backlog"]
    kind: Optional[Literal["unexplored", "variation", "challenge"]] = None
    question: str = Field(min_length=1)
    motivation: str = Field(min_length=1)
    belief: Optional[str] = None
    looks_like: str = ""
    sample_target: Optional[int] = Field(default=None, gt=0)
    decision_rule: str = ""
    opened: Optional[Stamp] = None
    replaces: Optional[str] = None
    outcome: Optional[Outcome] = None

    @model_validator(mode="after")
    def _complete(self) -> "Experiment":
        # A backlog idea only needs to say what and why; once it takes
        # production slots it must say how to recognise a story that serves
        # it, how many videos it needs and what result would answer it.
        if self.status != "backlog":
            missing = [
                name
                for name in (
                    "kind",
                    "looks_like",
                    "sample_target",
                    "decision_rule",
                    "opened",
                )
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(
                    f"{self.id} is {self.status} without {', '.join(missing)}"
                )
        if self.status == "closed" and self.outcome is None:
            raise ValueError(f"{self.id} is closed without an outcome")
        if self.kind == "challenge" and not self.belief:
            raise ValueError(f"{self.id} challenges a belief but names none")
        return self


class ExplorationPlan(_Record):
    """The share of production set aside to learn, and what it is spent on.

    The only tuning record the daily run reads.
    """

    cycle: int = Field(ge=0)
    share: float = Field(ge=0, le=0.5)
    share_since: Optional[date] = None
    min_fit: int = Field(default=70, ge=0, le=100)
    experiments: list[Experiment] = []

    def open(self) -> list[Experiment]:
        """The open experiments, highest priority first."""
        return [e for e in self.experiments if e.status == "open"]

    @classmethod
    def empty(cls) -> "ExplorationPlan":
        """No plan: nothing to explore, which is how the channel ran before."""
        return cls(cycle=0, share=0)


# -------------------------------------------------------------------- beliefs


class Evidence(_Record):
    videos: int = Field(ge=0)
    median_relative: Optional[float] = None
    period: Period


class BeliefEvent(_Record):
    date: date
    cycle: int = Field(ge=1)
    event: Literal[
        "entered",
        "confirmed",
        "weakened",
        "overturned",
        "retired",
        "kept_against_evidence",
    ]
    source: str = Field(min_length=1)
    note: str = ""


class Belief(_Record):
    """What the channel holds to be true, with the evidence behind it.

    The history only grows: every change of status adds the event that
    caused it, so a belief can be traced back to the reports that shaped it.
    """

    id: str = Field(pattern=r"^B\d{3}$")
    statement: str = Field(min_length=1)
    area: Area
    status: Literal["base", "does_not_work", "lead", "contested", "retired"]
    evidence: Evidence
    confidence: Confidence
    entered: Stamp
    last_tested: date
    history: list[BeliefEvent]

    @model_validator(mode="after")
    def _enough_evidence(self) -> "Belief":
        if (
            self.status in ("base", "does_not_work")
            and self.evidence.videos < EVIDENCE_MINIMUM
        ):
            raise ValueError(
                f"{self.id} is {self.status} on {self.evidence.videos} videos;"
                f" under {EVIDENCE_MINIMUM} it is a lead"
            )
        return self


# --------------------------------------------------------------------- cycles


class Justification(_Record):
    """What a prompt change rests on. A finding is named by its report's id."""

    kind: Literal["finding", "belief", "experiment"]
    ref: str = Field(min_length=1)
    summary: str = Field(min_length=1)


class PromptChange(_Record):
    prompt: PromptName
    before: str
    after: str
    justification: Justification
    decision: Literal["approved", "modified", "rejected"]
    reason: str = ""
    reverts: Optional[int] = None

    @model_validator(mode="after")
    def _rejection_explained(self) -> "PromptChange":
        if self.decision == "rejected" and not self.reason:
            raise ValueError(f"a rejected change to {self.prompt} has no reason")
        return self


class PromptVersions(_Record):
    story: Fingerprint
    evaluate_story: Fingerprint
    generate_hashtags: Fingerprint
    # None while the prompt does not exist.
    evaluate_exploration: Optional[Fingerprint] = None


class Settings(_Record):
    """What else shapes a video, so a cycle can tell whether more than the
    prompts changed."""

    writer_model: str
    grader_model: str
    rendering_strategy: str


class ExperimentChange(_Record):
    date: date
    report: str
    action: str
    experiment: Optional[str] = None
    note: str = ""


class OutsideChange(_Record):
    """A prompt edited outside the routine, found by the check and explained."""

    detected: date
    prompt: PromptName
    from_: str = Field(alias="from")
    to: str
    reason: str = Field(min_length=1)


class CycleEvaluation(_Record):
    result: Literal["helped", "hurt", "unclear", "not_evaluated"]
    base_videos: int = Field(ge=0)
    median_relative: Optional[float] = None
    previous_median_relative: Optional[float] = None
    note: str = ""


class Closing(_Record):
    recommendation: Action
    decision: Action
    note: str = ""


class Cycle(_Record):
    """A period with fixed editorial prompts, from one closing to the next."""

    number: int = Field(ge=1)
    opened: date
    deployed: Optional[date] = None
    closed: Optional[date] = None
    prompts: PromptVersions
    settings: Settings
    # The changes that opened this cycle; none for the first, the baseline.
    changes: list[PromptChange] = []
    experiment_changes: list[ExperimentChange] = []
    outside_changes: list[OutsideChange] = []
    evaluation: Optional[CycleEvaluation] = None
    reports: list[str] = []
    closing: Optional[Closing] = None

    @property
    def is_open(self) -> bool:
        return self.closed is None


# -------------------------------------------------------------------- reports


class Finding(_Record):
    statement: str = Field(min_length=1)
    area: Area
    direction: Literal["works", "does_not", "inconclusive"]
    videos: list[int]
    median_relative: Optional[float] = None
    confidence: Confidence
    is_lead: bool
    belief: Optional[str] = None
    unchanged_since: Optional[str] = None

    @model_validator(mode="after")
    def _small_is_a_lead(self) -> "Finding":
        if len(self.videos) < EVIDENCE_MINIMUM and not self.is_lead:
            raise ValueError(
                f"a finding on {len(self.videos)} videos must be a lead:"
                f" {self.statement}"
            )
        return self


class Excluded(_Record):
    unsettled: int = Field(ge=0)
    no_snapshot: int = Field(ge=0)
    ambiguous: int = Field(ge=0)


class VideoCount(_Record):
    considered: int = Field(ge=0)
    excluded: Excluded


class Distortion(_Record):
    kind: str
    note: str
    affects: str = ""


class ExperimentState(_Record):
    id: str
    settled: int = Field(ge=0)
    target: int = Field(gt=0)
    median_relative: Optional[float] = None


class CycleState(_Record):
    share_intended: float
    share_achieved: Optional[float] = None
    unfilled_slots: Optional[int] = None
    base_median_relative: Optional[float] = None
    experiments: list[ExperimentState] = []


class SincePrevious(_Record):
    previous: Optional[str] = None
    new_videos: int = Field(ge=0)
    changed_findings: list[str] = []


class Suggestion(_Record):
    question: str
    kind: Literal["unexplored", "variation", "challenge"]
    motivation: str
    decision: Literal["opened", "backlog", "discarded"]


class Recommendation(_Record):
    action: Action
    reasons: list[str] = Field(min_length=1)


class Decision(_Record):
    action: Action
    note: str = ""


class Report(_Record):
    """One reading of the history. Never rewritten: a correction is a new
    report that ``corrects`` it."""

    id: str = Field(pattern=r"^R-\d{4}-\d{2}-\d{2}(-\d+)?$")
    cycle: int = Field(ge=1)
    period: Period
    data_as_of: datetime
    videos: VideoCount
    distortions: list[Distortion] = []
    findings: list[Finding] = []
    cycle_state: CycleState
    since_previous: Optional[SincePrevious] = None
    suggestions: list[Suggestion] = []
    recommendation: Recommendation
    decision: Optional[Decision] = None
    corrects: Optional[str] = None
    view_url: Optional[str] = None


class StoryLabel(_Record):
    """How a video's story was classified, so every report groups it the same
    way. A reclassification is a newer label, not an edit."""

    record_id: int
    kind: str = Field(min_length=1)
    narrator_acts: str
    title_promise: str
    labelled_at: date
    note: str = ""
