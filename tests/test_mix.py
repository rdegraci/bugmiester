"""Seed mix recipes (beginner_mix / intermediate_mix / senior_mix)."""

from __future__ import annotations

from bugmiester.freshness import SEED_POOL, pick_seed
from bugmiester.mix import (
    BEGINNER_MIX_CATEGORIES,
    DEFAULT_MIX,
    SENIOR_MIX_CATEGORIES,
    SLOP_MIX_CATEGORIES,
    normalize_mix,
    slop_quota,
)


def test_normalize_mix_defaults_unknown_to_senior() -> None:
    assert normalize_mix("senior_mix") == "senior_mix"
    assert normalize_mix("beginner_mix") == "beginner_mix"
    assert normalize_mix("intermediate_mix") == "intermediate_mix"
    assert normalize_mix("nope") == DEFAULT_MIX
    assert normalize_mix(None) == DEFAULT_MIX


def test_senior_mix_fills_senior_then_slop() -> None:
    used: set[str] = set()
    cats: list[str] = []
    for _ in range(10):
        seed = pick_seed(
            SEED_POOL,
            used,
            mix="senior_mix",
            bugs_per_round=10,
        )
        used.add(seed.seed_id)
        cats.append(seed.category)
    quota = slop_quota(10)
    assert quota == 2
    assert all(cat in SENIOR_MIX_CATEGORIES for cat in cats[:-quota])
    assert all(cat in SLOP_MIX_CATEGORIES for cat in cats[-quota:])
    assert len(set(cats)) == 10


def test_beginner_mix_prefers_language_gotchas() -> None:
    used: set[str] = set()
    cats: list[str] = []
    for _ in range(10):
        seed = pick_seed(
            SEED_POOL,
            used,
            mix="beginner_mix",
            bugs_per_round=10,
        )
        used.add(seed.seed_id)
        cats.append(seed.category)
    assert all(cat in BEGINNER_MIX_CATEGORIES for cat in cats)
    assert len(set(cats)) == 10


def test_intermediate_mix_is_unweighted() -> None:
    used: set[str] = set()
    seed = pick_seed(
        SEED_POOL,
        used,
        mix="intermediate_mix",
        bugs_per_round=10,
    )
    assert seed.seed_id == SEED_POOL[0].seed_id
