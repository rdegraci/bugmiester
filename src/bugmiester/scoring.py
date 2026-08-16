"""Temporary simple scoring for Slice 05 (hybrid scoring comes later)."""

from __future__ import annotations

import re


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9+]+", _normalize(text)) if len(t) > 2}


def simple_keyword_score(
    expected_summary: str,
    answer: str,
    keywords: tuple[str, ...] | list[str] | None = None,
    *,
    points_possible: int = 10,
    partial_credit: bool = True,
) -> tuple[bool, bool, int, str]:
    """
    Return (correct, partial, points_awarded, feedback).

    Full credit when the answer contains enough keyword signal.
    Half credit on weak overlap when partial_credit is enabled.
    """
    answer_n = _normalize(answer)
    if not answer_n:
        return False, False, 0, "Empty answer."

    needles: list[str] = []
    if keywords:
        needles.extend(_normalize(k) for k in keywords if k.strip())
    # Also derive tokens from the canonical summary.
    summary_tokens = _tokens(expected_summary)
    needles.extend(sorted(summary_tokens))

    unique = []
    seen: set[str] = set()
    for item in needles:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)

    hits = 0
    for needle in unique:
        if " " in needle:
            if needle in answer_n:
                hits += 2
        elif needle in _tokens(answer_n) or needle in answer_n:
            hits += 1

    # Strong: phrase match or several token hits.
    strong = hits >= 3 or any(
        (" " in n and n in answer_n) for n in unique
    )
    weak = hits >= 1

    if strong:
        return (
            True,
            False,
            points_possible,
            f"Yes — {expected_summary}.",
        )
    if weak and partial_credit:
        half = max(1, points_possible // 2)
        return (
            False,
            True,
            half,
            f"Partially correct. Expected: {expected_summary}.",
        )
    return (
        False,
        False,
        0,
        f"Not quite. Expected: {expected_summary}.",
    )
