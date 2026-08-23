"""Adaptation clusters, miss counting, and adaptive phase scheduling."""

from __future__ import annotations

from bugmiester.adaptation import (
    ADAPTIVE_ACTION_NONE,
    ADAPTIVE_ACTION_REINFORCE,
    AnsweredBug,
    adaptive_action_for_pick,
    cluster_for_category,
    compute_gnarly_delay,
    count_cluster_misses,
    is_clear_miss,
    is_common_window_index,
    ISOLATION_CLUSTER_CATEGORIES,
    normalize_adaptive_cluster,
)
from bugmiester.freshness import SEED_POOL, pick_seed
from bugmiester.mix import adaptive_phase, is_gnarly_seed, senior_phase


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


def test_adaptive_phase_no_misses_matches_senior_phase() -> None:
    for bugs in (8, 10, 12):
        for used in range(bugs):
            assert adaptive_phase(
                used,
                bugs,
                mix="senior_mix",
                adaptation_enabled=True,
                cluster_misses=0,
            ) == senior_phase(used, bugs)


def test_adaptive_phase_delays_gnarly_when_threshold_met() -> None:
    # 10-bug senior round: gnarly normally at indices 8 and 9.
    assert adaptive_phase(
        8,
        10,
        mix="senior_mix",
        adaptation_enabled=True,
        cluster_misses=2,
        miss_threshold=2,
        max_delayed_gnarly=1,
    ) == "senior"
    assert adaptive_phase(
        9,
        10,
        mix="senior_mix",
        adaptation_enabled=True,
        cluster_misses=2,
        miss_threshold=2,
        max_delayed_gnarly=1,
    ) == "gnarly"


def test_compute_gnarly_delay_caps_and_keeps_one_gnarly() -> None:
    assert compute_gnarly_delay(1, 2, 1, 10) == 0
    assert compute_gnarly_delay(2, 2, 1, 10) == 1
    assert compute_gnarly_delay(5, 2, 1, 10) == 1
    assert compute_gnarly_delay(2, 2, 2, 10) == 1  # only 2 gnarly reserved; keep 1


def test_count_cluster_misses_common_window_only() -> None:
    bugs = [
        AnsweredBug(
            index=0,
            bug_category="concurrency",
            answered=True,
            correct=False,
            partial=False,
            player_answer="wrong",
        ),
        AnsweredBug(
            index=3,
            bug_category="concurrency",
            answered=True,
            correct=False,
            partial=False,
            player_answer="wrong",
        ),
        AnsweredBug(
            index=8,
            bug_category="concurrency",
            answered=True,
            correct=False,
            partial=False,
            player_answer="wrong",
        ),
    ]
    assert count_cluster_misses(bugs, "isolation", 10) == 1


def test_is_clear_miss_partial_upgrade_not_counted() -> None:
    assert is_clear_miss(
        AnsweredBug(
            index=3,
            bug_category="concurrency",
            answered=True,
            correct=True,
            partial=False,
        )
    ) is False
    assert is_clear_miss(
        AnsweredBug(
            index=3,
            bug_category="concurrency",
            answered=True,
            correct=False,
            partial=True,
            player_answer="idk",
        )
    ) is True


def test_pick_seed_reinforces_isolation_after_misses() -> None:
    used: set[str] = set()
    for _ in range(8):
        seed = pick_seed(
            SEED_POOL,
            used,
            mix="senior_mix",
            bugs_per_round=10,
            adaptation_enabled=True,
            cluster_misses=2,
            miss_threshold=2,
            max_delayed_gnarly=1,
        )
        used.add(seed.seed_id)
    reinforce = pick_seed(
        SEED_POOL,
        used,
        mix="senior_mix",
        bugs_per_round=10,
        adaptation_enabled=True,
        cluster_misses=2,
        miss_threshold=2,
        max_delayed_gnarly=1,
    )
    assert not is_gnarly_seed(reinforce)
    assert reinforce.category in ISOLATION_CLUSTER_CATEGORIES


def test_pick_seed_gnarly_when_no_misses() -> None:
    used: set[str] = set()
    for _ in range(8):
        used.add(
            pick_seed(
                SEED_POOL,
                used,
                mix="senior_mix",
                bugs_per_round=10,
                adaptation_enabled=True,
                cluster_misses=0,
            ).seed_id
        )
    gnarly = pick_seed(
        SEED_POOL,
        used,
        mix="senior_mix",
        bugs_per_round=10,
        adaptation_enabled=True,
        cluster_misses=0,
    )
    assert is_gnarly_seed(gnarly)


def test_adaptive_action_reinforce_on_delayed_slot() -> None:
    delay = compute_gnarly_delay(2, 2, 1, 10)
    phase = adaptive_phase(
        8,
        10,
        mix="senior_mix",
        adaptation_enabled=True,
        cluster_misses=2,
    )
    assert adaptive_action_for_pick(8, 10, phase, delay) == ADAPTIVE_ACTION_REINFORCE
    assert adaptive_action_for_pick(9, 10, "gnarly", delay) == ADAPTIVE_ACTION_NONE


def test_is_common_window_index() -> None:
    assert is_common_window_index(3, 10)
    assert not is_common_window_index(0, 10)
    assert not is_common_window_index(9, 10)


def test_adaptive_action_none_constant() -> None:
    assert ADAPTIVE_ACTION_NONE == "none"
