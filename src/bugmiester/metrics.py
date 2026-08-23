"""Per-round / per-bug latency and call counters → Application Support logs."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bugmiester.adaptation import ADAPTIVE_ACTION_NONE, ADAPTIVE_ACTIONS


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class BugMetrics:
    snippet_id: str
    index: int
    seed_id: str = ""
    generate_ms: float = 0.0
    submit_ms: float | None = None
    generate_attempts: int = 1
    freshness_rejects: int = 0
    judge_called: bool = False
    degraded: bool = False
    provider: str = ""
    model: str = ""
    bug_category: str = ""
    cluster: str | None = None
    adaptive_action: str = ADAPTIVE_ACTION_NONE
    points_awarded: int | None = None
    correct: bool | None = None
    partial: bool | None = None


@dataclass
class RoundMetrics:
    round_id: str
    bugs_per_round: int
    provider: str
    model: str
    started_at: str = field(default_factory=_utc_now_iso)
    completed_at: str | None = None
    round_score: int = 0
    round_possible: int = 100
    bugs: list[BugMetrics] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MetricsCollector:
    """In-memory per-round metrics; flush JSON under Application Support logs/."""

    def __init__(self) -> None:
        self._rounds: dict[str, RoundMetrics] = {}

    def start_round(
        self,
        round_id: str,
        *,
        bugs_per_round: int,
        provider: str,
        model: str,
        round_possible: int,
    ) -> RoundMetrics:
        record = RoundMetrics(
            round_id=round_id,
            bugs_per_round=bugs_per_round,
            provider=provider,
            model=model,
            round_possible=round_possible,
        )
        self._rounds[round_id] = record
        return record

    def get(self, round_id: str) -> RoundMetrics | None:
        return self._rounds.get(round_id)

    def record_generate(
        self,
        round_id: str,
        *,
        snippet_id: str,
        index: int,
        seed_id: str,
        generate_ms: float,
        generate_attempts: int,
        freshness_rejects: int,
        degraded: bool,
        provider: str,
        model: str,
        bug_category: str = "",
        cluster: str | None = None,
        adaptive_action: str = ADAPTIVE_ACTION_NONE,
    ) -> BugMetrics:
        action = (
            adaptive_action
            if adaptive_action in ADAPTIVE_ACTIONS
            else ADAPTIVE_ACTION_NONE
        )
        round_metrics = self._require(round_id)
        bug = BugMetrics(
            snippet_id=snippet_id,
            index=index,
            seed_id=seed_id,
            generate_ms=generate_ms,
            generate_attempts=generate_attempts,
            freshness_rejects=freshness_rejects,
            degraded=degraded,
            provider=provider,
            model=model,
            bug_category=str(bug_category or "").strip(),
            cluster=cluster,
            adaptive_action=action,
        )
        round_metrics.bugs.append(bug)
        return bug

    def record_submit(
        self,
        round_id: str,
        snippet_id: str,
        *,
        submit_ms: float,
        judge_called: bool,
        points_awarded: int,
        correct: bool,
        partial: bool,
        round_score: int,
    ) -> BugMetrics | None:
        round_metrics = self._rounds.get(round_id)
        if round_metrics is None:
            return None
        for bug in round_metrics.bugs:
            if bug.snippet_id == snippet_id:
                bug.submit_ms = submit_ms
                bug.judge_called = judge_called
                bug.points_awarded = points_awarded
                bug.correct = correct
                bug.partial = partial
                round_metrics.round_score = round_score
                return bug
        return None

    def record_recovery(
        self,
        round_id: str,
        snippet_id: str,
        *,
        points_awarded: int,
        correct: bool,
        partial: bool,
        round_score: int,
    ) -> BugMetrics | None:
        round_metrics = self._rounds.get(round_id)
        if round_metrics is None:
            return None
        for bug in round_metrics.bugs:
            if bug.snippet_id == snippet_id:
                bug.points_awarded = points_awarded
                bug.correct = correct
                bug.partial = partial
                round_metrics.round_score = round_score
                return bug
        return None

    def flush_round(
        self,
        logs_dir: Path,
        round_id: str,
        *,
        round_score: int | None = None,
    ) -> Path | None:
        """
        Write round metrics JSON under ``logs_dir``.

        Returns the written path, or None if the round was never tracked.
        """
        round_metrics = self._rounds.get(round_id)
        if round_metrics is None:
            return None
        if round_score is not None:
            round_metrics.round_score = round_score
        round_metrics.completed_at = _utc_now_iso()

        logs_dir.mkdir(parents=True, exist_ok=True)
        path = logs_dir / f"round_{round_id}.json"
        path.write_text(
            json.dumps(round_metrics.to_dict(), indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        return path

    def _require(self, round_id: str) -> RoundMetrics:
        record = self._rounds.get(round_id)
        if record is None:
            raise KeyError(f"Unknown round_id for metrics: {round_id}")
        return record
