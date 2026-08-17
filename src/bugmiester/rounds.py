"""In-memory round / answer-key / history store."""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field

from bugmiester.config import Settings
from bugmiester.fallback_snippets import fallback_for_seed
from bugmiester.freshness import (
    SEED_POOL,
    GeneratedSnippet,
    HistoryEntry,
    generate_with_freshness,
    history_entry,
)
from bugmiester.llm.mock_provider import MockProvider
from bugmiester.models import (
    NextBugResponse,
    RoundStartResponse,
    RoundSummary,
    SubmitResponse,
)
from bugmiester.scoring import simple_keyword_score


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
        self._mock = MockProvider()
        self._history: deque[HistoryEntry] = deque(maxlen=history_maxlen)

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

        provider = settings.llm.provider
        if provider != "mock":
            raise RoundError(
                "provider_unsupported",
                f"Provider '{provider}' is not wired yet. Set llm.provider to mock.",
                status_code=503,
            )

        generated, degraded, attempts, rejects = generate_with_freshness(
            used_seed_ids=state.used_seed_ids,
            history=list(self._history),
            seed_pool=SEED_POOL,
            max_attempts=settings.freshness.max_generate_attempts,
            similarity_threshold=settings.freshness.similarity_reject_threshold,
            avoid_list_max=settings.freshness.avoid_list_max,
            use_fallback=settings.resilience.use_canned_fallback_on_generate_exhaustion,
            generate_fn=self._mock.generate_for_seed,
            fallback_fn=fallback_for_seed,
        )
        stored = self._store_generated(
            state,
            generated,
            degraded=degraded,
            attempts=attempts,
            rejects=rejects,
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

        points_possible = state.points_per_bug
        correct, partial, awarded, feedback = simple_keyword_score(
            stored.bug_summary,
            answer,
            stored.keywords,
            points_possible=points_possible,
            partial_credit=settings.scoring.partial_credit,
        )

        stored.answered = True
        state.round_score += awarded
        if correct:
            state.correct_count += 1
        elif partial:
            state.partial_count += 1
        else:
            state.incorrect_count += 1

        answered_index = stored.index
        state.index += 1
        state.pending = None
        round_complete = state.index >= state.bugs_per_round
        if round_complete:
            state.complete = True

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
            correct=correct,
            partial=partial,
            points_awarded=awarded,
            points_possible=points_possible,
            round_score=state.round_score,
            round_possible=state.bugs_per_round * state.points_per_bug,
            index=answered_index,
            bugs_per_round=state.bugs_per_round,
            feedback=feedback,
            expected_summary=stored.bug_summary,
            round_complete=round_complete,
            summary=summary,
        )

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
