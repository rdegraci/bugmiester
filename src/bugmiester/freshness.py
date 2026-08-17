"""Scenario seeds, avoid-list, normalize + similarity reject."""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class ScenarioSeed:
    seed_id: str
    category: str
    setting: str
    constraint: str | None = None

    @property
    def theme(self) -> str:
        base = f"{self.category}: {self.setting}"
        if self.constraint:
            return f"{base} ({self.constraint})"
        return base


# Curated pool — at least one distinct seed per bug in a default round of 10.
SEED_POOL: tuple[ScenarioSeed, ...] = (
    ScenarioSeed("opt-dict-force", "optionals", "dictionary lookup"),
    ScenarioSeed("col-empty-avg", "collections", "empty array average"),
    ScenarioSeed("ref-class-copy", "value vs reference", "class mistaken for value type"),
    ScenarioSeed("flow-switch-int", "control flow", "non-exhaustive switch"),
    ScenarioSeed("err-async-try", "errors", "async networking decode"),
    ScenarioSeed("col-off-by-one", "collections", "table selection index"),
    ScenarioSeed("opt-greet-print", "optionals", "login form greeting"),
    ScenarioSeed("err-try-optional", "errors", "file URL write"),
    ScenarioSeed("conc-actor-mut", "concurrency", "timer callback bump", "must involve actor"),
    ScenarioSeed("val-let-struct", "value vs reference", "immutable point"),
    ScenarioSeed("opt-array-first", "optionals", "first element access"),
    ScenarioSeed("conc-await-miss", "concurrency", "missing await on async call"),
)


@dataclass(frozen=True)
class HistoryEntry:
    bug_summary: str
    bug_category: str
    theme: str
    code: str
    normalized_code: str


def history_entry(
    *,
    bug_summary: str,
    bug_category: str,
    theme: str,
    code: str,
) -> HistoryEntry:
    return HistoryEntry(
        bug_summary=bug_summary,
        bug_category=bug_category,
        theme=theme,
        code=code,
        normalized_code=normalize_code(code),
    )


@dataclass(frozen=True)
class GeneratedSnippet:
    code: str
    bug_summary: str
    bug_category: str
    difficulty: str
    hints: tuple[str, ...]
    keywords: tuple[str, ...]
    seed: ScenarioSeed


def normalize_code(code: str) -> str:
    """Strip comments and excess whitespace for similarity checks."""
    text = code.replace("\r\n", "\n")
    # Remove // line comments and /* */ blocks (simple).
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    lines: list[str] = []
    for line in text.split("\n"):
        if "//" in line:
            line = line[: line.index("//")]
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"\s+", " ", text).strip().lower()
    return text


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9_]+", text.lower()) if len(t) > 1}


def token_jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def difflib_ratio(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def similarity_score(code_a: str, summary_a: str, code_b: str, summary_b: str) -> float:
    """Combined similarity in [0, 1] over normalized code and summaries."""
    na, nb = normalize_code(code_a), normalize_code(code_b)
    code_sim = max(difflib_ratio(na, nb), token_jaccard(na, nb))
    sum_sim = max(
        difflib_ratio(summary_a.lower(), summary_b.lower()),
        token_jaccard(summary_a, summary_b),
    )
    return max(code_sim, sum_sim)


def is_too_similar(
    code: str,
    bug_summary: str,
    history: Sequence[HistoryEntry],
    threshold: float,
) -> bool:
    for entry in history:
        score = similarity_score(code, bug_summary, entry.code, entry.bug_summary)
        if score >= threshold:
            return True
    return False


def build_avoid_list(
    history: Sequence[HistoryEntry],
    *,
    max_items: int,
) -> list[HistoryEntry]:
    if max_items <= 0:
        return []
    return list(history[-max_items:])


def pick_seed(
    pool: Sequence[ScenarioSeed],
    used_seed_ids: set[str],
) -> ScenarioSeed:
    for seed in pool:
        if seed.seed_id not in used_seed_ids:
            return seed
    # Pool exhausted within the round — reuse least-recent by cycling.
    if not pool:
        raise ValueError("SEED_POOL is empty")
    return pool[len(used_seed_ids) % len(pool)]


GenerateFn = Callable[[ScenarioSeed, Sequence[HistoryEntry]], GeneratedSnippet]
FallbackFn = Callable[[ScenarioSeed], GeneratedSnippet]


def generate_with_freshness(
    *,
    used_seed_ids: set[str],
    history: Sequence[HistoryEntry],
    seed_pool: Sequence[ScenarioSeed] = SEED_POOL,
    max_attempts: int = 2,
    similarity_threshold: float = 0.72,
    avoid_list_max: int = 20,
    use_fallback: bool = True,
    generate_fn: GenerateFn,
    fallback_fn: FallbackFn,
) -> tuple[GeneratedSnippet, bool, int, int]:
    """
    Pick a seed, generate with retries on near-duplicates, else fallback.

    Returns (snippet, degraded, attempts_used, freshness_rejects).
    """
    seed = pick_seed(seed_pool, used_seed_ids)
    used_seed_ids.add(seed.seed_id)
    avoid = build_avoid_list(history, max_items=avoid_list_max)

    attempts = 0
    rejects = 0
    last: GeneratedSnippet | None = None

    while attempts < max_attempts:
        attempts += 1
        candidate = generate_fn(seed, avoid)
        last = candidate
        if not is_too_similar(
            candidate.code,
            candidate.bug_summary,
            avoid,
            similarity_threshold,
        ):
            return candidate, False, attempts, rejects
        rejects += 1
        # Stricter avoid-list for next attempt: include rejected summary as synthetic entry.
        avoid = list(avoid) + [
            history_entry(
                bug_summary=candidate.bug_summary,
                bug_category=candidate.bug_category,
                theme=seed.theme,
                code=candidate.code,
            )
        ]

    if use_fallback:
        fallback = fallback_fn(seed)
        return fallback, True, attempts, rejects

    if last is not None:
        # Last resort without fallback flag: return last attempt undegraded.
        return last, False, attempts, rejects
    raise RuntimeError("generate_with_freshness produced no candidate")
