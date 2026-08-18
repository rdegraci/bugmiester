"""Hybrid keyword + LLM judge scoring."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from bugmiester.config import ScoringSettings
from bugmiester.llm.base import JudgeResult as JudgeResult

# Confidence at or below this is "low" for generosity.
LOW_CONFIDENCE_THRESHOLD = 0.5

# Re-export for call sites / tests that import from scoring.
__all__ = [
    "JudgeResult",
    "ScoreResult",
    "keyword_match_tier",
    "score_answer",
    "score_keyword",
    "simple_keyword_score",
]

JudgeFn = Callable[[str, str, str], JudgeResult]


@dataclass(frozen=True)
class ScoreResult:
    """Outcome of scoring one player answer."""

    correct: bool
    partial: bool
    points_awarded: int
    points_possible: int
    feedback: str
    expected_summary: str
    judge_called: bool = False


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9+]+", _normalize(text)) if len(t) > 2}


def _half_points(points_possible: int) -> int:
    return max(1, points_possible // 2) if points_possible > 0 else 0


def _dedupe(items: Sequence[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = _normalize(item)
        if key and key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def keyword_match_tier(
    expected_summary: str,
    answer: str,
    keywords: Sequence[str] | None = None,
    *,
    bug_category: str | None = None,
) -> str:
    """
    Classify keyword overlap: ``strong`` | ``weak`` | ``miss``.

    Strong: multi-word phrase hit, or several distinct keyword/summary tokens.
    Weak: at least one meaningful token/phrase overlap.
    Miss: empty answer or no overlap.
    """
    answer_n = _normalize(answer)
    if not answer_n:
        return "miss"

    needles: list[str] = []
    if keywords:
        needles.extend(k for k in keywords if k and k.strip())
    if bug_category:
        needles.append(bug_category)
    needles.extend(sorted(_tokens(expected_summary)))

    unique = _dedupe(needles)
    answer_tokens = _tokens(answer_n)

    hits = 0
    phrase_hit = False
    for needle in unique:
        if " " in needle:
            if needle in answer_n:
                hits += 2
                phrase_hit = True
        elif needle in answer_tokens or needle in answer_n:
            hits += 1

    if phrase_hit or hits >= 3:
        return "strong"
    if hits >= 1:
        return "weak"
    return "miss"


def score_keyword(
    expected_summary: str,
    answer: str,
    keywords: Sequence[str] | None = None,
    *,
    bug_category: str | None = None,
    points_possible: int = 10,
    partial_credit: bool = True,
) -> ScoreResult:
    """Keyword-only scoring with optional half-credit partials."""
    tier = keyword_match_tier(
        expected_summary, answer, keywords, bug_category=bug_category
    )

    if tier == "strong":
        return ScoreResult(
            correct=True,
            partial=False,
            points_awarded=points_possible,
            points_possible=points_possible,
            feedback="Yes.",
            expected_summary=expected_summary,
        )
    if tier == "weak" and partial_credit:
        return ScoreResult(
            correct=False,
            partial=True,
            points_awarded=_half_points(points_possible),
            points_possible=points_possible,
            feedback="Partially correct.",
            expected_summary=expected_summary,
        )
    if not _normalize(answer):
        feedback = "Empty answer."
    else:
        feedback = "Not quite."
    return ScoreResult(
        correct=False,
        partial=False,
        points_awarded=0,
        points_possible=points_possible,
        feedback=feedback,
        expected_summary=expected_summary,
    )


def _apply_generosity(
    result: JudgeResult,
    *,
    expected_summary: str,
    points_possible: int,
    scoring: ScoringSettings,
) -> tuple[bool, bool, int, str]:
    """Map judge output to points; soften low-confidence misses when configured."""
    correct = result.correct
    partial = result.partial and not correct
    feedback = result.feedback
    confidence = result.confidence

    prefer_partial = (
        scoring.generosity == "prefer_partial_on_low_confidence"
        and scoring.partial_credit
        and confidence <= LOW_CONFIDENCE_THRESHOLD
    )

    if prefer_partial and not correct and not partial:
        partial = True
        feedback = (
            result.feedback.strip()
            or "Close enough — we're giving partial credit."
        )

    if correct:
        return True, False, points_possible, feedback or "Yes."
    if partial:
        return (
            False,
            True,
            _half_points(points_possible),
            feedback or "Partially correct.",
        )
    return (
        False,
        False,
        0,
        feedback or "Not quite.",
    )


def _from_judge(
    judge: JudgeResult,
    *,
    expected_summary: str,
    points_possible: int,
    scoring: ScoringSettings,
    judge_called: bool,
) -> ScoreResult:
    correct, partial, awarded, feedback = _apply_generosity(
        judge,
        expected_summary=expected_summary,
        points_possible=points_possible,
        scoring=scoring,
    )
    return ScoreResult(
        correct=correct,
        partial=partial,
        points_awarded=awarded,
        points_possible=points_possible,
        feedback=feedback,
        expected_summary=expected_summary,
        judge_called=judge_called,
    )


def score_answer(
    *,
    code: str,
    expected_summary: str,
    answer: str,
    keywords: Sequence[str] | None = None,
    bug_category: str | None = None,
    scoring: ScoringSettings,
    max_judge_calls: int = 1,
    judge_fn: JudgeFn | None = None,
) -> ScoreResult:
    """
    Score a player answer.

    Modes (``scoring.mode``):
    - ``keyword`` — keywords only
    - ``llm_judge`` — judge only (capped by ``max_judge_calls``)
    - ``hybrid`` (default) — strong/weak keywords first; judge on miss
    """
    points_possible = scoring.points_per_bug
    mode = (scoring.mode or "hybrid").strip().lower()
    allowed_calls = max(0, max_judge_calls)

    def call_judge() -> ScoreResult:
        if allowed_calls < 1 or judge_fn is None:
            return ScoreResult(
                correct=False,
                partial=False,
                points_awarded=0,
                points_possible=points_possible,
                feedback="Not quite.",
                expected_summary=expected_summary,
                judge_called=False,
            )
        judged = judge_fn(code, expected_summary, answer)
        return _from_judge(
            judged,
            expected_summary=expected_summary,
            points_possible=points_possible,
            scoring=scoring,
            judge_called=True,
        )

    if mode == "llm_judge":
        return call_judge()

    keyword_result = score_keyword(
        expected_summary,
        answer,
        keywords,
        bug_category=bug_category,
        points_possible=points_possible,
        partial_credit=scoring.partial_credit,
    )

    if mode == "keyword":
        return keyword_result

    # hybrid (default): accept strong/weak keyword outcomes; judge only on miss
    if keyword_result.correct or keyword_result.partial:
        return keyword_result
    return call_judge()


# Back-compat alias used by early Slice 05 call sites / tests.
def simple_keyword_score(
    expected_summary: str,
    answer: str,
    keywords: Sequence[str] | None = None,
    *,
    points_possible: int = 10,
    partial_credit: bool = True,
) -> tuple[bool, bool, int, str]:
    result = score_keyword(
        expected_summary,
        answer,
        keywords,
        points_possible=points_possible,
        partial_credit=partial_credit,
    )
    return result.correct, result.partial, result.points_awarded, result.feedback
