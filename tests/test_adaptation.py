"""Phase 1: adaptation clusters and adaptive_phase stub."""

from __future__ import annotations

from bugmiester.adaptation import (
    ADAPTIVE_ACTION_NONE,
    cluster_for_category,
    normalize_adaptive_cluster,
)
from bugmiester.mix import adaptive_phase, senior_phase


def test_cluster_for_category_isolation() -> None:
    assert cluster_for_category("concurrency") == "isolation"
    assert cluster_for_category("MainActor") == "isolation"
    assert cluster_for_category("sendable") == "isolation"
    assert cluster_for_category("optionals") is None
    assert cluster_for_category("") is None


def test_normalize_adaptive_cluster_unknown_falls_back() -> None:
    assert normalize_adaptive_cluster("isolation") == "isolation"
    assert normalize_adaptive_cluster("nope") == "isolation"
    assert normalize_adaptive_cluster(None) == "isolation"


def test_adaptive_phase_disabled_matches_senior_phase() -> None:
    for bugs in (8, 10, 12):
        for used in range(bugs):
            assert adaptive_phase(
                used,
                bugs,
                mix="senior_mix",
                adaptation_enabled=False,
            ) == senior_phase(used, bugs)


def test_adaptive_phase_enabled_phase1_still_matches_senior_phase() -> None:
    """Phase 1 stub: enabled flag does not change scheduling yet."""
    for bugs in (8, 10, 12):
        for used in range(bugs):
            assert adaptive_phase(
                used,
                bugs,
                mix="senior_mix",
                adaptation_enabled=True,
            ) == senior_phase(used, bugs)


def test_adaptive_phase_non_senior_mix_ignores_enabled() -> None:
    assert adaptive_phase(0, 10, mix="beginner_mix", adaptation_enabled=True) == "slop"
    assert adaptive_phase(5, 10, mix="intermediate_mix", adaptation_enabled=True) == "senior"


def test_adaptive_action_none_constant() -> None:
    assert ADAPTIVE_ACTION_NONE == "none"
