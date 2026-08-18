"""In-memory round / answer-key / history store."""

from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field

from bugmiester.config import Settings
from bugmiester.freshness import GeneratedSnippet, HistoryEntry, history_entry
from bugmiester.llm import generate_bug, judge_answer
from bugmiester.llm.anthropic_provider import (
    AnthropicConfigError,
    AnthropicRequestError,
)
from bugmiester.llm.openai_provider import OpenAIConfigError, OpenAIRequestError
from bugmiester.metrics import MetricsCollector
from bugmiester.models import (
    NextBugResponse,
    ReportSnippetResponse,
    RoundStartResponse,
    RoundSummary,
    SubmitResponse,
)
from bugmiester.reports import write_report
from bugmiester.scoring import score_answer

_LIVE_PROVIDERS = frozenset({"openai", "anthropic"})
_PROVIDER_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def _assert_provider_ready(settings: Settings) -> None:
    provider = (settings.llm.provider or "").strip().lower()
    if provider == "mock":
        return
    if provider in _LIVE_PROVIDERS:
        if not settings.config_ready:
            env_name = _PROVIDER_ENV[provider]
            raise RoundError(
                "config_not_ready",
                f"Set {env_name} in {settings.env_path}",
                status_code=503,
            )
        return
    raise RoundError(
        "provider_unsupported",
        (
            f"Provider '{provider}' is not wired yet. "
            "Set llm.provider to mock, openai, or anthropic."
        ),
        status_code=503,
    )


def _judge_fn_for(settings: Settings):
    provider = (settings.llm.provider or "").strip().lower()
    if provider in {"mock", *_LIVE_PROVIDERS}:

        def _judge(code: str, expected: str, ans: str):
            return judge_answer(code, expected, ans, settings)

        return _judge
    return None


def _map_provider_error(exc: Exception) -> RoundError | None:
    if isinstance(exc, (OpenAIConfigError, AnthropicConfigError)):
        return RoundError("config_not_ready", str(exc), status_code=503)
    if isinstance(exc, (OpenAIRequestError, AnthropicRequestError)):
        return RoundError("llm_failed", str(exc), status_code=502)
    if isinstance(exc, NotImplementedError):
        return RoundError("provider_unsupported", str(exc), status_code=503)
    return None


@dataclass
class StoredSnippet:
    snippet_id: str
    index: int
    language: str
    code: str
    difficulty: str
    degraded: bool
    bug_summary: str
    bug_category: str
    hints: tuple[str, ...]
    keywords: tuple[str, ...]
    seed_id: str = ""
    answered: bool = False
    generate_attempts: int = 1
    freshness_rejects: int = 0
    player_answer: str = ""
    points_awarded: int | None = None
    points_possible: int | None = None
    correct: bool | None = None
    partial: bool | None = None
    judge_called: bool = False
    reported: bool = False


@dataclass
class RoundState:
    round_id: str
    bugs_per_round: int
    points_per_bug: int
    language: str
    index: int = 0  # next bug index to serve / current open bug index
    round_score: int = 0
    correct_count: int = 0
    partial_count: int = 0
    incorrect_count: int = 0
    pending: StoredSnippet | None = None
    snippets: dict[str, StoredSnippet] = field(default_factory=dict)
    used_seed_ids: set[str] = field(default_factory=set)
    complete: bool = False


class RoundStore:
    def __init__(self, history_maxlen: int = 200) -> None:
        self._rounds: dict[str, RoundState] = {}
        self._history: deque[HistoryEntry] = deque(maxlen=history_maxlen)
        self.metrics = MetricsCollector()

    def start(self, settings: Settings) -> RoundStartResponse:
        round_id = str(uuid.uuid4())
        bugs = settings.game.bugs_per_round
        points = settings.scoring.points_per_bug
        state = RoundState(
            round_id=round_id,
            bugs_per_round=bugs,
            points_per_bug=points,
            language=settings.game.language,
        )
        self._rounds[round_id] = state
        if settings.metrics.log_per_bug:
            self.metrics.start_round(
                round_id,
                bugs_per_round=bugs,
                provider=settings.llm.provider,
                model=settings.llm.model,
                round_possible=bugs * points,
            )
        return RoundStartResponse(
            round_id=round_id,
            bugs_per_round=bugs,
            index=0,
            round_score=0,
            round_possible=bugs * points,
        )

    def get(self, round_id: str) -> RoundState | None:
        return self._rounds.get(round_id)

    def next_bug(self, round_id: str, settings: Settings) -> NextBugResponse:
        state = self._require(round_id)
        if state.complete:
            raise RoundError("round_complete", "This round is already complete")
        if state.pending is not None and not state.pending.answered:
            raise RoundError(
                "pending_answer",
                "Submit the current bug before requesting the next one",
            )
        if state.index >= state.bugs_per_round:
            raise RoundError("round_complete", "No more bugs in this round")

        _assert_provider_ready(settings)

        started = time.perf_counter()
        try:
            outcome = generate_bug(
                settings,
                used_seed_ids=state.used_seed_ids,
                history=list(self._history),
            )
        except Exception as exc:
            mapped = _map_provider_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        generate_ms = (time.perf_counter() - started) * 1000.0
        generated = outcome.as_generated_snippet()
        degraded = outcome.degraded
        attempts = outcome.attempts
        rejects = outcome.freshness_rejects

        stored = self._store_generated(
            state,
            generated,
            degraded=degraded,
            attempts=attempts,
            rejects=rejects,
        )
        if settings.metrics.log_per_bug:
            self.metrics.record_generate(
                round_id,
                snippet_id=stored.snippet_id,
                index=stored.index,
                seed_id=stored.seed_id,
                generate_ms=generate_ms,
                generate_attempts=attempts,
                freshness_rejects=rejects,
                degraded=degraded,
                provider=settings.llm.provider,
                model=settings.llm.model,
            )
        return NextBugResponse(
            round_id=round_id,
            index=state.index,
            bugs_per_round=state.bugs_per_round,
            snippet_id=stored.snippet_id,
            language=stored.language,
            code=stored.code,
            difficulty=stored.difficulty,
            degraded=stored.degraded,
        )

    def _store_generated(
        self,
        state: RoundState,
        generated: GeneratedSnippet,
        *,
        degraded: bool,
        attempts: int,
        rejects: int,
    ) -> StoredSnippet:
        snippet_id = str(uuid.uuid4())
        stored = StoredSnippet(
            snippet_id=snippet_id,
            index=state.index,
            language=state.language,
            code=generated.code,
            difficulty=generated.difficulty,
            degraded=degraded,
            bug_summary=generated.bug_summary,
            bug_category=generated.bug_category,
            hints=generated.hints,
            keywords=generated.keywords,
            seed_id=generated.seed.seed_id,
            generate_attempts=attempts,
            freshness_rejects=rejects,
        )
        state.pending = stored
        state.snippets[snippet_id] = stored
        self._history.append(
            history_entry(
                bug_summary=generated.bug_summary,
                bug_category=generated.bug_category,
                theme=generated.seed.theme,
                code=generated.code,
            )
        )
        return stored

    def submit(
        self,
        round_id: str,
        snippet_id: str,
        answer: str,
        settings: Settings,
    ) -> SubmitResponse:
        state = self._require(round_id)
        if state.complete:
            raise RoundError("round_complete", "This round is already complete")

        stored = state.snippets.get(snippet_id)
        if stored is None:
            raise RoundError("unknown_snippet", "Unknown snippet_id", status_code=404)
        if stored.answered:
            raise RoundError("already_answered", "This snippet was already answered")
        if state.pending is None or state.pending.snippet_id != snippet_id:
            raise RoundError(
                "not_pending",
                "This snippet is not the active pending bug",
            )

        judge_fn = _judge_fn_for(settings)

        started = time.perf_counter()
        try:
            scored = score_answer(
                code=stored.code,
                expected_summary=stored.bug_summary,
                answer=answer,
                keywords=stored.keywords,
                bug_category=stored.bug_category,
                scoring=settings.scoring,
                max_judge_calls=settings.resilience.max_judge_calls_per_submit,
                judge_fn=judge_fn,
            )
        except Exception as exc:
            mapped = _map_provider_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        submit_ms = (time.perf_counter() - started) * 1000.0

        stored.answered = True
        stored.player_answer = answer
        stored.points_awarded = scored.points_awarded
        stored.points_possible = scored.points_possible
        stored.correct = scored.correct
        stored.partial = scored.partial
        stored.judge_called = scored.judge_called

        state.round_score += scored.points_awarded
        if scored.correct:
            state.correct_count += 1
        elif scored.partial:
            state.partial_count += 1
        else:
            state.incorrect_count += 1

        if settings.metrics.log_per_bug:
            self.metrics.record_submit(
                round_id,
                snippet_id,
                submit_ms=submit_ms,
                judge_called=scored.judge_called,
                points_awarded=scored.points_awarded,
                correct=scored.correct,
                partial=scored.partial,
                round_score=state.round_score,
            )

        answered_index = stored.index
        state.index += 1
        state.pending = None
        round_complete = state.index >= state.bugs_per_round
        if round_complete:
            state.complete = True
            if settings.metrics.log_per_bug:
                self.metrics.flush_round(
                    settings.logs_dir,
                    round_id,
                    round_score=state.round_score,
                )

        summary = None
        if round_complete:
            summary = RoundSummary(
                round_score=state.round_score,
                round_possible=state.bugs_per_round * state.points_per_bug,
                correct_count=state.correct_count,
                partial_count=state.partial_count,
                incorrect_count=state.incorrect_count,
            )

        return SubmitResponse(
            correct=scored.correct,
            partial=scored.partial,
            points_awarded=scored.points_awarded,
            points_possible=scored.points_possible,
            round_score=state.round_score,
            round_possible=state.bugs_per_round * state.points_per_bug,
            index=answered_index,
            bugs_per_round=state.bugs_per_round,
            feedback=scored.feedback,
            expected_summary=scored.expected_summary,
            round_complete=round_complete,
            summary=summary,
        )

    def report_snippet(
        self,
        round_id: str,
        snippet_id: str,
        reason: str,
        note: str,
        settings: Settings,
    ) -> ReportSnippetResponse:
        if not settings.reports.enabled:
            raise RoundError("reports_disabled", "Snippet reports are disabled")

        state = self._require(round_id)
        stored = state.snippets.get(snippet_id)
        if stored is None:
            raise RoundError("unknown_snippet", "Unknown snippet_id", status_code=404)
        if not stored.answered:
            raise RoundError(
                "not_answered",
                "Report is only available after feedback for this snippet",
            )

        try:
            write_report(
                settings.reports_dir,
                round_id=round_id,
                snippet_id=snippet_id,
                reason=reason,
                note=note,
                code=stored.code,
                bug_summary=stored.bug_summary,
                bug_category=stored.bug_category,
                seed_id=stored.seed_id,
                player_answer=stored.player_answer,
                points_awarded=stored.points_awarded,
                points_possible=stored.points_possible,
                correct=stored.correct,
                partial=stored.partial,
                provider=settings.llm.provider,
                model=settings.llm.model,
                degraded=stored.degraded,
            )
        except ValueError as exc:
            raise RoundError("invalid_reason", str(exc), status_code=400) from exc

        stored.reported = True
        return ReportSnippetResponse(ok=True)

    def summary(self, round_id: str) -> RoundSummary:
        state = self._require(round_id)
        return RoundSummary(
            round_score=state.round_score,
            round_possible=state.bugs_per_round * state.points_per_bug,
            correct_count=state.correct_count,
            partial_count=state.partial_count,
            incorrect_count=state.incorrect_count,
        )

    def _require(self, round_id: str) -> RoundState:
        state = self._rounds.get(round_id)
        if state is None:
            raise RoundError("unknown_round", "Unknown round_id", status_code=404)
        return state


class RoundError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
