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


# Same-claim rewrites of the official summary (not nearby wrong claims).
_PARAPHRASE_OVERLAP = 0.72


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
    if overlap >= _PARAPHRASE_OVERLAP:
        return True
    smaller = min(len(cand_tok), len(exp_tok))
    containment = len(cand_tok & exp_tok) / smaller
    return containment >= 0.9 and overlap >= 0.4


def seed_bank_entries() -> tuple[tuple[str, str], ...]:
    """``(bug_summary, bug_category)`` from mock/seed banks, then canned lines."""
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for snip in (*MOCK_SNIPPETS, *SEED_SNIPPETS.values()):
        key = _normalize(snip.bug_summary)
        if key and key not in seen:
            seen.add(key)
            out.append((snip.bug_summary, snip.bug_category))
    for canned in CANNED_DISTRACTORS:
        key = _normalize(canned)
        if key and key not in seen:
            seen.add(key)
            out.append((canned, ""))
    return tuple(out)


def seed_bank_summaries() -> tuple[str, ...]:
    return tuple(summary for summary, _category in seed_bank_entries())


def filter_distractors(
    candidates: list[str],
    expected: str,
    *,
    needed: int,
    player_answer: str = "",
) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    expected_key = _normalize(expected)

    def _try_add(raw: str) -> None:
        text = str(raw).strip()
        key = _normalize(text)
        if not key or key == expected_key or key in seen:
            return
        if too_close_to_expected(text, expected):
            return
        seen.add(key)
        unique.append(text)

    if player_answer.strip():
        _try_add(player_answer)
    for item in candidates:
        if len(unique) >= needed:
            break
        _try_add(item)
    return unique[:needed]


def fill_from_seed_bank(
    expected: str,
    already: list[str],
    *,
    needed: int,
    bug_category: str | None = None,
    player_answer: str = "",
) -> list[str]:
    have = filter_distractors(
        already, expected, needed=needed, player_answer=player_answer
    )
    have_keys = {_normalize(x) for x in have}
    cat = (bug_category or "").strip().lower()
    entries = list(seed_bank_entries())
    if cat:
        same = [entry for entry in entries if entry[1].strip().lower() == cat]
        other = [entry for entry in entries if entry[1].strip().lower() != cat]
        entries = same + other
    for summary, _category in entries:
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
