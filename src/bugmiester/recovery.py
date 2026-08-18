"""Partial-credit recovery quiz: distractors, shuffle, option ids."""

from __future__ import annotations

import random
import re
import uuid
from dataclasses import dataclass

from bugmiester.llm.mock_provider import MOCK_SNIPPETS, SEED_SNIPPETS

RECOVERY_PROMPT = (
    "Partial credit. Pick the precise bug for full points, "
    "or continue to keep the partial."
)

# Extra wrong answers when the snippet bank is short or too similar.
CANNED_DISTRACTORS: tuple[str, ...] = (
    "Integer overflow when the counter wraps past Int.max",
    "Retain cycle from a strong self capture in a closure",
    "Main-thread UI work is missing; this should hop to the main actor",
    "Comparing floating-point values with == instead of a tolerance",
    "Using NSNumber bridging where a native Int was required",
    "String interpolation inserts Optional(...) because the value is optional",
    "Dictionary keys are compared by identity instead of Equatable",
    "A lazy var is never initialized because the first access is skipped",
    "Codable decode fails because a Date is not given a custom strategy",
    "Array copy-on-write is broken by an unexpected class wrapper",
)


@dataclass(frozen=True)
class RecoveryOption:
    """Server-side choice. ``correct`` never leaves the process on submit."""

    option_id: str
    text: str
    correct: bool


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9+]+", _normalize(text)) if len(t) > 2}


def too_close_to_expected(candidate: str, expected: str) -> bool:
    """True when a distractor is a paraphrase of the real bug summary."""
    cand_n = _normalize(candidate)
    exp_n = _normalize(expected)
    if not cand_n or not exp_n:
        return True
    if cand_n == exp_n:
        return True
    if cand_n in exp_n or exp_n in cand_n:
        return True
    cand_tok = _tokens(candidate)
    exp_tok = _tokens(expected)
    if not cand_tok or not exp_tok:
        return True
    overlap = len(cand_tok & exp_tok) / len(cand_tok | exp_tok)
    return overlap >= 0.55


def seed_bank_summaries() -> tuple[str, ...]:
    seen: set[str] = set()
    out: list[str] = []
    for snip in (*MOCK_SNIPPETS, *SEED_SNIPPETS.values()):
        key = _normalize(snip.bug_summary)
        if key and key not in seen:
            seen.add(key)
            out.append(snip.bug_summary)
    for canned in CANNED_DISTRACTORS:
        key = _normalize(canned)
        if key and key not in seen:
            seen.add(key)
            out.append(canned)
    return tuple(out)


def filter_distractors(
    candidates: list[str],
    expected: str,
    *,
    needed: int,
) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    expected_key = _normalize(expected)
    for item in candidates:
        text = str(item).strip()
        key = _normalize(text)
        if not key or key == expected_key or key in seen:
            continue
        if too_close_to_expected(text, expected):
            continue
        seen.add(key)
        unique.append(text)
        if len(unique) >= needed:
            break
    return unique


def fill_from_seed_bank(expected: str, already: list[str], *, needed: int) -> list[str]:
    have = list(already)
    have_keys = {_normalize(x) for x in have}
    for summary in seed_bank_summaries():
        if len(have) >= needed:
            break
        key = _normalize(summary)
        if key in have_keys:
            continue
        if too_close_to_expected(summary, expected):
            continue
        have.append(summary)
        have_keys.add(key)
    return have[:needed]


def assemble_options(
    expected: str,
    distractors: list[str],
    *,
    choice_count: int,
) -> list[RecoveryOption] | None:
    needed = max(1, choice_count - 1)
    if len(distractors) < needed:
        return None
    options = [
        RecoveryOption(
            option_id=str(uuid.uuid4()),
            text=expected.strip(),
            correct=True,
        )
    ]
    for text in distractors[:needed]:
        options.append(
            RecoveryOption(
                option_id=str(uuid.uuid4()),
                text=text.strip(),
                correct=False,
            )
        )
    random.shuffle(options)
    return options


def public_choices(options: list[RecoveryOption]) -> list[dict[str, str]]:
    return [{"id": opt.option_id, "text": opt.text} for opt in options]


def strip_expected_from_feedback(feedback: str, expected: str) -> str:
    """Hide the answer key in partial feedback while a quiz is open."""
    text = (feedback or "").strip()
    expected_n = expected.strip()
    if expected_n and expected_n in text:
        text = text.replace(expected_n, "").strip(" .:—-")
        text = re.sub(r"(?i)\bexpected:?\s*$", "", text).strip(" .:—-")
    if not text or text.lower() in {"partially correct", "partial"}:
        return "Partial credit."
    if "expected" in text.lower():
        return "Partial credit."
    return text
