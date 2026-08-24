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


def adaptive_phase(
    used_count: int,
    bugs_per_round: int,
    *,
    mix: str = DEFAULT_MIX,
    adaptation_enabled: bool = False,
    cluster_misses: int = 0,
    miss_threshold: int = 2,
    max_delayed_gnarly: int = 1,
) -> str:
    """
    Return the mix band for the next bug at ``used_count`` (0-based index).

    Bands: ``slop`` | ``senior`` | ``gnarly`` (same names as ``senior_phase``).

    When adaptation is enabled on ``senior_mix``, Common-band cluster misses can
    postpone up to ``max_delayed_gnarly`` Gnarly slots (keeping at least one).
    """
    if not adaptation_enabled or normalize_mix(mix) != "senior_mix":
        return senior_phase(used_count, bugs_per_round)

    from bugmiester.adaptation import compute_gnarly_delay

    delay = compute_gnarly_delay(
        cluster_misses,
        miss_threshold,
        max_delayed_gnarly,
        bugs_per_round,
    )
    slop = slop_quota(bugs_per_round)
    gnarly = gnarly_quota(bugs_per_round)
    effective_gnarly = gnarly - delay if delay > 0 else gnarly
    if used_count < slop:
        return "slop"
    if effective_gnarly > 0 and used_count >= bugs_per_round - effective_gnarly:
        return "gnarly"
    return "senior"


def is_gnarly_seed(seed: object) -> bool:
    """Reentrancy, exclusivity, or allowlisted hard concurrency / MainActor costumes."""
    seed_id = getattr(seed, "seed_id", None)
    if seed_id in GNARLY_SEED_IDS:
        return True
    category = getattr(seed, "category", None)
    return category in {"actor reentrancy", "exclusivity"}


def difficulty_label(
    mix: object,
    index: int,
    bugs_per_round: int,
    *,
    adaptation_enabled: bool = False,
    cluster_misses: int = 0,
    miss_threshold: int = 2,
    max_delayed_gnarly: int = 1,
) -> str:
    """Player-facing band for the current bug, or empty when the mix does not ramp."""
    if normalize_mix(mix) != "senior_mix":
        return ""
    phase = adaptive_phase(
        index,
        bugs_per_round,
        mix=str(mix),
        adaptation_enabled=adaptation_enabled,
        cluster_misses=cluster_misses,
        miss_threshold=miss_threshold,
        max_delayed_gnarly=max_delayed_gnarly,
    )
    return BAND_LABELS[phase]


def preferred_categories(
    mix: str,
    used_seeds: Sequence[object],
    *,
    bugs_per_round: int,
    adaptation_enabled: bool = False,
    cluster_misses: int = 0,
    miss_threshold: int = 2,
    max_delayed_gnarly: int = 1,
    adaptation_cluster: str = "isolation",
    cross_round_first_common_bias: bool = False,
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

    phase = adaptive_phase(
        len(used_seeds),
        bugs_per_round,
        mix=profile,
        adaptation_enabled=adaptation_enabled,
        cluster_misses=cluster_misses,
        miss_threshold=miss_threshold,
        max_delayed_gnarly=max_delayed_gnarly,
    )
    if phase == "slop":
        return SLOP_MIX_CATEGORIES
    if phase == "gnarly":
        return GNARLY_CATEGORIES

    if (
        cross_round_first_common_bias
        and phase == "senior"
        and len(used_seeds) == slop_quota(bugs_per_round)
    ):
        from bugmiester.adaptation import cluster_category_set

        bias = cluster_category_set(adaptation_cluster) & SENIOR_CORE_CATEGORIES
        if bias:
            return bias

    from bugmiester.adaptation import (
        cluster_category_set,
        compute_gnarly_delay,
        is_reinforcement_slot,
    )

    delay = 0
    if adaptation_enabled and profile == "senior_mix":
        delay = compute_gnarly_delay(
            cluster_misses,
            miss_threshold,
            max_delayed_gnarly,
            bugs_per_round,
        )
    if is_reinforcement_slot(len(used_seeds), bugs_per_round, delay):
        reinforce = cluster_category_set(adaptation_cluster) & SENIOR_CORE_CATEGORIES
        if reinforce:
            return reinforce
    return SENIOR_CORE_CATEGORIES
