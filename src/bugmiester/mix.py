"""Round mix recipes: which categories to prefer. Not snippet difficulty tags."""

from __future__ import annotations

from collections.abc import Sequence

MIX_PROFILES = frozenset({"beginner_mix", "intermediate_mix", "senior_mix"})
DEFAULT_MIX = "senior_mix"

BEGINNER_MIX_CATEGORIES = frozenset(
    {
        "optionals",
        "collections",
        "enums",
        "type casting",
        "failable init",
        "string indexes",
        "control flow",
        "errors",
        "result",
        "Sequence slices",
        "access control",
        "value vs reference",
        "inout / COW",
        "defer",
    }
)

SENIOR_MIX_CATEGORIES = frozenset(
    {
        "SwiftUI state",
        "SwiftUI environment",
        "Combine",
        "MainActor",
        "concurrency",
        "sendable",
        "Task cancellation",
        "actor reentrancy",
        "captures",
        "unowned",
        "exclusivity",
        "protocol witnesses",
        "some vs any",
    }
)

SLOP_MIX_CATEGORIES = frozenset(
    {
        "optionals",
        "errors",
        "collections",
        "type casting",
        "failable init",
    }
)


def normalize_mix(raw: object) -> str:
    name = str(raw or DEFAULT_MIX).strip().lower()
    if name in MIX_PROFILES:
        return name
    return DEFAULT_MIX


def slop_quota(bugs_per_round: int) -> int:
    """How many beginner LLM/legacy slop bugs to keep in a senior round."""
    if bugs_per_round <= 1:
        return 0
    if bugs_per_round < 8:
        return 1
    return 2


def preferred_categories(
    mix: str,
    used_seeds: Sequence[object],
    *,
    bugs_per_round: int,
) -> frozenset[str] | None:
    """
    Category set to try first, or None for an unweighted (intermediate) draw.

    ``used_seeds`` items need a ``.category`` attribute (ScenarioSeed).
    """
    profile = normalize_mix(mix)
    if profile == "intermediate_mix":
        return None
    if profile == "beginner_mix":
        return BEGINNER_MIX_CATEGORIES

    used_count = len(used_seeds)
    remaining = max(0, bugs_per_round - used_count)
    quota = slop_quota(bugs_per_round)
    slop_picked = sum(
        1
        for seed in used_seeds
        if getattr(seed, "category", None) in SLOP_MIX_CATEGORIES
    )
    slop_needed = max(0, quota - slop_picked)
    if slop_needed > 0 and remaining <= slop_needed:
        return SLOP_MIX_CATEGORIES
    return SENIOR_MIX_CATEGORIES
