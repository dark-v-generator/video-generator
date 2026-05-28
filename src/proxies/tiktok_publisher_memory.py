"""Per-run memory for the TikTok publisher agent.

Owns two responsibilities:

1. **Run capture** — after every agent run (success OR failure) we write
   a structured snapshot of what the agent did to
   ``.storage/tiktok_runs/<ts>-<outcome>.json`` plus a human-readable
   ``<ts>-<outcome>.md`` trace alongside it. Per step we record:

   * ``thinking``     — the model's chain of thought
   * ``eval``         — the model's verdict on the previous step
   * ``memory``       — what the model believes it has done so far
   * ``next_goal``    — what the model is about to do
   * ``actions``      — the concrete actions dispatched
   * ``results``      — outcomes of those actions (success / error)

   This is enough to answer "what did the agent decide, why, and what
   did it do" without having to dig through the raw bootstrap log.

2. **Lessons file** — ``.storage/tiktok_learnings.md`` is a HUMAN-ONLY
   document. We seed it once from ``assets/tiktok_seed_lessons.md`` on
   first run, and we leave it alone after that. Edits are manual; sync
   with ``just push-tiktok-learnings`` / ``just tiktok-lessons``. There
   is intentionally NO LLM-based reflector — auto-generated lessons
   tend to be plausible-sounding but wrong, and they pollute the prompt.

Goals
-----
* Capture is best-effort: any failure logs a warning but never breaks
  publishing.
* No external API calls (no OpenRouter / litellm). Capture is all local
  string formatting + file IO.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from src.core.logging_config import get_logger

# Repo-relative path to the seed lessons file (computed against this
# module so the same code works whether installed or run from source).
_SEED_LESSONS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "assets" / "tiktok_seed_lessons.md"
)


@dataclass
class StepRecord:
    """One agent step, in our own normalized shape."""

    step: int
    thinking: str = ""
    eval: str = ""
    memory: str = ""
    next_goal: str = ""
    actions: List[dict] = field(default_factory=list)
    results: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "thinking": self.thinking,
            "eval": self.eval,
            "memory": self.memory,
            "next_goal": self.next_goal,
            "actions": self.actions,
            "results": self.results,
        }


@dataclass
class RunRecord:
    """Compact, JSON-serializable view of one agent run."""

    timestamp: str
    video_path: str
    description: str
    schedule_at: Optional[str]
    outcome: str
    final_result: str
    errors: List[str]
    urls_visited: List[str]
    step_count: int
    steps: List[StepRecord]
    raw_llm_failure_artifact: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "video_path": self.video_path,
            "description": self.description,
            "schedule_at": self.schedule_at,
            "outcome": self.outcome,
            "final_result": self.final_result,
            "errors": self.errors,
            "urls_visited": self.urls_visited,
            "step_count": self.step_count,
            "steps": [s.to_dict() for s in self.steps],
            "raw_llm_failure_artifact": self.raw_llm_failure_artifact,
        }


class TikTokPublisherMemory:
    """Owns per-run capture + the seed lessons bootstrap.

    Layout under ``base_dir`` (typically ``.storage/``):

    * ``tiktok_runs/<ts>-<outcome>.json``   one structured file per run
    * ``tiktok_runs/<ts>-<outcome>.md``     human-readable trace twin
    * ``tiktok_learnings.md``               seeded from assets, then
                                            HUMAN-ONLY (no auto writes)
    """

    def __init__(self, base_dir: Path) -> None:
        self._logger = get_logger(__name__)
        self._base_dir = Path(base_dir).expanduser().resolve()
        self._runs_dir = self._base_dir / "tiktok_runs"
        self._lessons_path = self._base_dir / "tiktok_learnings.md"

        self._base_dir.mkdir(parents=True, exist_ok=True)
        self._runs_dir.mkdir(parents=True, exist_ok=True)
        self._maybe_seed_lessons()

        # Live JSONL log path for the current run. Set by start_live_log()
        # at the beginning of publish_video() and appended to per step
        # via the agent's register_new_step_callback. Survives crashes —
        # even if the process is killed mid-run, all completed steps are
        # already on disk in this file.
        self._live_log_path: Optional[Path] = None
        self._llm_failure_artifact_path: Optional[Path] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def start_live_log(
        self,
        video_path: str,
        description: str,
        schedule_at: Optional[datetime],
    ) -> Path:
        """Open a per-run live JSONL log and write a header line.

        Returns the path. Subsequent ``append_live_step()`` calls write
        to this same file. Each line is a complete JSON object so the
        file remains parseable even if the process is killed mid-write.
        """
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        self._live_log_path = self._runs_dir / f"{ts}.live.jsonl"
        self._llm_failure_artifact_path = None
        header = {
            "type": "header",
            "ts": datetime.now().isoformat(timespec="seconds"),
            "video_path": video_path,
            "description": description,
            "schedule_at": schedule_at.isoformat() if schedule_at else None,
        }
        self._append_jsonl(self._live_log_path, header)
        return self._live_log_path

    def record_llm_failure_artifact(self, path: Path) -> None:
        """Remember the raw LLM failure artifact path for this run."""
        self._llm_failure_artifact_path = path

    def append_live_step(self, step: dict) -> None:
        """Append one step record to the live log. Best-effort.

        Called from the agent's ``register_new_step_callback``. We do
        not raise on write errors — losing a step record must NEVER
        crash the agent run.
        """
        if self._live_log_path is None:
            return
        try:
            self._append_jsonl(
                self._live_log_path,
                {"type": "step", "ts": datetime.now().isoformat(timespec="seconds"), **step},
            )
        except Exception as exc:
            self._logger.warning("Live log append failed: %s", exc)

    @staticmethod
    def _append_jsonl(path: Path, record: dict) -> None:
        """Append a single JSON line to a file with explicit flush."""
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with path.open("a", encoding="utf-8") as f:
            f.write(line)
            f.flush()

    def load_lessons(self) -> str:
        """Return the lessons file contents (for human inspection only).

        Note: as of the move to a self-contained task prompt, lessons
        are NO LONGER auto-injected into the agent's task. This method
        exists for ``just tiktok-lessons`` and tests.
        """
        if not self._lessons_path.exists():
            return ""
        return self._lessons_path.read_text(encoding="utf-8").strip()

    def capture_run(
        self,
        history: Any,
        outcome: str,
        video_path: str,
        description: str,
        schedule_at: Optional[datetime],
    ) -> Optional[Path]:
        """Persist a structured + human-readable snapshot of one run.

        Returns the JSON path written, or None if serialization failed.
        Best-effort: on any exception we log and return None — the
        publishing flow keeps going regardless.
        """
        try:
            record = self._build_record(
                history=history,
                outcome=outcome,
                video_path=video_path,
                description=description,
                schedule_at=schedule_at,
            )
            timestamp_slug = record.timestamp.replace(":", "").replace("-", "")[:14]
            outcome_slug = re.sub(r"[^a-z0-9_-]+", "_", record.outcome.lower())[:30]
            base = self._runs_dir / f"{timestamp_slug}-{outcome_slug}"

            json_path = base.with_suffix(".json")
            json_path.write_text(
                json.dumps(record.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            md_path = base.with_suffix(".md")
            md_path.write_text(self._render_markdown(record), encoding="utf-8")

            self._logger.info(
                "TikTok memory: captured run -> %s (+ %s)",
                json_path.name,
                md_path.name,
            )
            return json_path
        except Exception as exc:
            self._logger.warning("TikTok memory: capture failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _maybe_seed_lessons(self) -> None:
        """Bootstrap lessons file from the seed if it does not exist."""
        if self._lessons_path.exists():
            return
        if _SEED_LESSONS_PATH.exists():
            self._lessons_path.write_text(
                _SEED_LESSONS_PATH.read_text(encoding="utf-8"), encoding="utf-8"
            )
            self._logger.info(
                "TikTok memory: seeded lessons from %s", _SEED_LESSONS_PATH.name
            )

    def _build_record(
        self,
        history: Any,
        outcome: str,
        video_path: str,
        description: str,
        schedule_at: Optional[datetime],
    ) -> RunRecord:
        timestamp = datetime.now().isoformat(timespec="seconds")

        urls_visited: List[str] = []
        errors: List[str] = []
        final_result = ""
        steps: List[StepRecord] = []

        try:
            urls_attr = getattr(history, "urls", None)
            if callable(urls_attr):
                urls_visited = [str(u) for u in (urls_attr() or []) if u]
        except Exception:
            pass

        try:
            errs_attr = getattr(history, "errors", None)
            if callable(errs_attr):
                errors = [str(e) for e in (errs_attr() or []) if e]
        except Exception:
            pass

        try:
            final = getattr(history, "final_result", None)
            if callable(final):
                final_result = str(final() or "")
        except Exception:
            pass

        try:
            history_list = getattr(history, "history", None) or []
            for i, step in enumerate(history_list, start=1):
                steps.append(self._extract_step(i, step))
        except Exception as exc:
            self._logger.warning("Step extraction failed: %s", exc)

        return RunRecord(
            timestamp=timestamp,
            video_path=video_path,
            description=description,
            schedule_at=schedule_at.isoformat() if schedule_at else None,
            outcome=outcome,
            final_result=final_result[:1000],
            errors=[e[:600] for e in errors[:30]],
            urls_visited=urls_visited[:50],
            step_count=len(steps),
            steps=steps,
            raw_llm_failure_artifact=(
                str(self._llm_failure_artifact_path)
                if self._llm_failure_artifact_path is not None
                else None
            ),
        )

    @staticmethod
    def _safe_str(val: Any, limit: int = 600) -> str:
        if val is None:
            return ""
        s = str(val)
        return s if len(s) <= limit else s[:limit] + "..."

    def _extract_step(self, step_num: int, step: Any) -> StepRecord:
        """Pull thinking/eval/memory/goal/actions/results out of one step.

        browser-use 0.7.x exposes ``model_output`` (an ``AgentOutput``
        pydantic model) and ``result`` (a list of ``ActionResult``).
        We grab common fields defensively — if a field name changes
        across versions we just leave it blank rather than crashing.
        """
        rec = StepRecord(step=step_num)

        model_output = getattr(step, "model_output", None)
        if model_output is not None:
            for src, dest in (
                ("thinking", "thinking"),
                ("evaluation_previous_goal", "eval"),
                ("memory", "memory"),
                ("next_goal", "next_goal"),
            ):
                val = getattr(model_output, src, None)
                if val is not None:
                    setattr(rec, dest, self._safe_str(val, limit=2000))

            try:
                actions = getattr(model_output, "action", None) or []
                rec.actions = [self._serialize_action(a) for a in actions][:20]
            except Exception:
                pass

        try:
            results = getattr(step, "result", None) or []
            rec.results = [self._serialize_result(r) for r in results][:20]
        except Exception:
            pass

        return rec

    def _serialize_action(self, action: Any) -> dict:
        """Convert one action descriptor to a small dict."""
        try:
            if hasattr(action, "model_dump"):
                d = action.model_dump(exclude_none=True)
                # browser-use's action is a discriminated union with one
                # populated field — extract that into name + params for
                # easier reading.
                if isinstance(d, dict) and len(d) == 1:
                    name, params = next(iter(d.items()))
                    return {"name": name, "params": params}
                return d
            if isinstance(action, dict):
                return action
            return {"raw": self._safe_str(action, limit=400)}
        except Exception as exc:
            return {"_error": self._safe_str(exc, limit=200)}

    def _serialize_result(self, result: Any) -> dict:
        """Convert one ActionResult to a small dict."""
        try:
            if hasattr(result, "model_dump"):
                d = result.model_dump(exclude_none=True)
                # Trim the verbose fields
                for key in ("extracted_content", "long_term_memory", "error"):
                    if key in d and isinstance(d[key], str):
                        d[key] = self._safe_str(d[key], limit=400)
                return d
            return {"raw": self._safe_str(result, limit=400)}
        except Exception as exc:
            return {"_error": self._safe_str(exc, limit=200)}

    # ------------------------------------------------------------------
    # Markdown rendering for human review
    # ------------------------------------------------------------------
    def _render_markdown(self, record: RunRecord) -> str:
        """Render a human-friendly markdown trace.

        Layout: header with metadata, errors block (if any), then one
        section per step showing eval / next_goal / actions / results.
        """
        lines: List[str] = []
        lines.append(f"# TikTok run · {record.timestamp}")
        lines.append("")
        lines.append(f"- **Outcome:** `{record.outcome}`")
        lines.append(f"- **Video:** `{record.video_path}`")
        lines.append(f"- **Description:** {record.description}")
        if record.schedule_at:
            lines.append(f"- **Schedule at:** {record.schedule_at}")
        lines.append(f"- **Steps:** {record.step_count}")
        if record.raw_llm_failure_artifact:
            lines.append(
                f"- **LLM failure artifact:** `{record.raw_llm_failure_artifact}`"
            )
        if record.final_result:
            lines.append("")
            lines.append("## Final result")
            lines.append("```")
            lines.append(record.final_result)
            lines.append("```")
        if record.errors:
            lines.append("")
            lines.append(f"## Errors ({len(record.errors)})")
            for err in record.errors:
                lines.append(f"- {err}")

        lines.append("")
        lines.append("## Steps")

        for step in record.steps:
            lines.append("")
            lines.append(f"### Step {step.step}")
            if step.eval:
                lines.append(f"- **Eval (of previous step):** {step.eval}")
            if step.thinking:
                lines.append(f"- **Thinking:** {step.thinking}")
            if step.memory:
                lines.append(f"- **Memory:** {step.memory}")
            if step.next_goal:
                lines.append(f"- **Next goal:** {step.next_goal}")
            if step.actions:
                lines.append("- **Actions dispatched:**")
                for a in step.actions:
                    lines.append(f"  - `{self._fmt_action(a)}`")
            if step.results:
                lines.append("- **Results:**")
                for r in step.results:
                    lines.append(f"  - `{self._fmt_result(r)}`")

        if record.urls_visited:
            lines.append("")
            lines.append(f"## URLs visited ({len(record.urls_visited)})")
            seen = set()
            for url in record.urls_visited:
                if url in seen:
                    continue
                seen.add(url)
                lines.append(f"- {url}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _fmt_action(action: dict) -> str:
        if "name" in action:
            params = action.get("params") or {}
            params_str = ", ".join(f"{k}={v!r}" for k, v in params.items())
            return f"{action['name']}({params_str})"
        return json.dumps(action, ensure_ascii=False)

    @staticmethod
    def _fmt_result(result: dict) -> str:
        # Pick the most useful one of (error / long_term_memory / extracted_content)
        if "error" in result and result["error"]:
            return f"ERROR: {result['error']}"
        if "long_term_memory" in result and result["long_term_memory"]:
            return result["long_term_memory"]
        if "extracted_content" in result and result["extracted_content"]:
            return result["extracted_content"]
        return json.dumps(result, ensure_ascii=False)


__all__ = ["TikTokPublisherMemory", "RunRecord", "StepRecord"]
