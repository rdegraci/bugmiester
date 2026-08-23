"""Adaptive round scheduling: cluster map (Phase 1). Phase logic lives in mix.py."""

from __future__ import annotations

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
