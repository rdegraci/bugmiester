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

# Held out of the Common middle so slots 9–10 can use them.
# Ordinary "concurrency" stays in SENIOR_CORE; only allowlisted hard
# concurrency costumes (see GNARLY_SEED_IDS / is_gnarly_seed) are gnarly.
GNARLY_CATEGORIES = frozenset(
    {
        "actor reentrancy",
        "exclusivity",
    }
)

GNARLY_SEED_IDS = frozenset(
    {
        "conc-continuation-stuck",
        "conc-continuation-double",
        "conc-taskgroup-early",
        "main-await-hop",
        "send-actor-task-race",
    }
)

SENIOR_CORE_CATEGORIES = frozenset(
    SENIOR_MIX_CATEGORIES - GNARLY_CATEGORIES
)

BAND_LABELS = {
    "slop": "Simple",
    "senior": "Common",
    "gnarly": "Gnarly",
}


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


def gnarly_quota(bugs_per_round: int) -> int:
    """How many end-of-round gnarly costumes to reserve in a senior round."""
    if bugs_per_round >= 10:
        return 2
    if bugs_per_round >= 8:
        return 1
    return 0


def senior_phase(used_count: int, bugs_per_round: int) -> str:
    """slop → senior core → gnarly, by 0-based index in the round."""
    slop = slop_quota(bugs_per_round)
    gnarly = gnarly_quota(bugs_per_round)
    if used_count < slop:
        return "slop"
    if gnarly and used_count >= bugs_per_round - gnarly:
        return "gnarly"
    return "senior"


def is_gnarly_seed(seed: object) -> bool:
    """Reentrancy, exclusivity, or allowlisted hard concurrency / MainActor costumes."""
    seed_id = getattr(seed, "seed_id", None)
    if seed_id in GNARLY_SEED_IDS:
        return True
    category = getattr(seed, "category", None)
    return category in {"actor reentrancy", "exclusivity"}


def difficulty_label(mix: object, index: int, bugs_per_round: int) -> str:
    """Player-facing band for the current bug, or empty when the mix does not ramp."""
    if normalize_mix(mix) != "senior_mix":
        return ""
    return BAND_LABELS[senior_phase(index, bugs_per_round)]


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

    phase = senior_phase(len(used_seeds), bugs_per_round)
    if phase == "slop":
        return SLOP_MIX_CATEGORIES
    if phase == "gnarly":
        return GNARLY_CATEGORIES
    return SENIOR_CORE_CATEGORIES
