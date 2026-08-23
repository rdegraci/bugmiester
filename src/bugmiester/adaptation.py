"""Adaptive round scheduling: cluster map and miss accounting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from bugmiester.mix import gnarly_quota, senior_phase

# Player-facing adaptive actions logged per bug (see docs/ADAPTATION-PLAN.md).
ADAPTIVE_ACTION_NONE = "none"
ADAPTIVE_ACTION_REINFORCE = "reinforce"
ADAPTIVE_ACTION_DELAYED_GNARLY = "delayed_gnarly"

ADAPTIVE_ACTIONS = frozenset(
    {
        ADAPTIVE_ACTION_NONE,
        ADAPTIVE_ACTION_REINFORCE,
        ADAPTIVE_ACTION_DELAYED_GNARLY,
    }
)

# v1: only isolation is adapted; more clusters can register here later.
ADAPTIVE_CLUSTERS = frozenset({"isolation"})

DEFAULT_ADAPTIVE_CLUSTER = "isolation"

ISOLATION_CLUSTER_CATEGORIES = frozenset(
    {
        "MainActor",
        "sendable",
        "concurrency",
    }
)

CLUSTER_CATEGORIES: dict[str, frozenset[str]] = {
    "isolation": ISOLATION_CLUSTER_CATEGORIES,
}

ADAPTATION_CLUSTER_HINTS: dict[str, str] = {
    "isolation": "Extra practice on isolation before Gnarly.",
}


@dataclass(frozen=True)
class AnsweredBug:
    """Minimal per-bug view for within-round adaptation (no answer key leakage)."""

    index: int
    bug_category: str
    answered: bool = False
    correct: bool | None = None
    partial: bool | None = None
    recovery_open: bool = False
    player_answer: str = ""


def normalize_adaptive_cluster(raw: object) -> str:
    """Return a known cluster id; unknown values fall back to isolation."""
    name = str(raw or DEFAULT_ADAPTIVE_CLUSTER).strip().lower()
    if name in ADAPTIVE_CLUSTERS:
        return name
    return DEFAULT_ADAPTIVE_CLUSTER


def cluster_for_category(category: str) -> str | None:
    """Map a bug category to a concept cluster, or None when not clustered."""
    cat = str(category or "").strip()
    if not cat:
        return None
    for cluster_id, categories in CLUSTER_CATEGORIES.items():
        if cat in categories:
            return cluster_id
    return None


def adaptation_hint_for_action(action: str, cluster: str) -> str:
    """Player-facing coach line when adaptation schedules reinforcement."""
    if action != ADAPTIVE_ACTION_REINFORCE:
        return ""
    return ADAPTATION_CLUSTER_HINTS.get(
        normalize_adaptive_cluster(cluster), ""
    )


def cluster_category_set(cluster: str) -> frozenset[str]:
    return CLUSTER_CATEGORIES.get(normalize_adaptive_cluster(cluster), frozenset())


def is_common_window_index(index: int, bugs_per_round: int) -> bool:
    """True when the bug index is in the base Common band (not Simple / Gnarly)."""
    return senior_phase(index, bugs_per_round) == "senior"


def is_clear_miss(bug: AnsweredBug) -> bool:
    """True for incorrect, give-up, or partial without recovery upgrade."""
    from bugmiester.scoring import is_give_up_answer

    if bug.correct:
        return False
    if is_give_up_answer(bug.player_answer):
        return True
    if bug.partial:
        return not bug.correct
    return True


def count_cluster_misses(
    bugs: Sequence[AnsweredBug],
    cluster: str,
    bugs_per_round: int,
) -> int:
    """Count clear misses on clustered categories in the base Common window."""
    categories = cluster_category_set(cluster)
    if not categories:
        return 0
    total = 0
    for bug in bugs:
        if not bug.answered or bug.recovery_open:
            continue
        if not is_common_window_index(bug.index, bugs_per_round):
            continue
        if bug.bug_category not in categories:
            continue
        if is_clear_miss(bug):
            total += 1
    return total


def compute_gnarly_delay(
    cluster_misses: int,
    miss_threshold: int,
    max_delayed_gnarly: int,
    bugs_per_round: int,
) -> int:
    """
    How many reserved Gnarly slots to postpone when reinforcement is warranted.

    Always leaves at least one Gnarly slot when the round reserves any.
    """
    if cluster_misses < miss_threshold:
        return 0
    gnarly = gnarly_quota(bugs_per_round)
    if gnarly <= 0:
        return 0
    cap = min(max(0, max_delayed_gnarly), gnarly - 1)
    if cap <= 0:
        return 0
    excess = cluster_misses - miss_threshold + 1
    return min(cap, excess)


def is_reinforcement_slot(
    used_count: int,
    bugs_per_round: int,
    gnarly_delay: int,
) -> bool:
    """True when this pick is an extra Common slot that replaced a reserved Gnarly slot."""
    if gnarly_delay <= 0:
        return False
    base_start = bugs_per_round - gnarly_quota(bugs_per_round)
    return base_start <= used_count < base_start + gnarly_delay


def adaptive_action_for_pick(
    used_count: int,
    bugs_per_round: int,
    phase: str,
    gnarly_delay: int,
) -> str:
    if phase == "senior" and is_reinforcement_slot(
        used_count, bugs_per_round, gnarly_delay
    ):
        return ADAPTIVE_ACTION_REINFORCE
    return ADAPTIVE_ACTION_NONE
