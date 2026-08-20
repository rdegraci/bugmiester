"""Seed mix recipes (beginner_mix / intermediate_mix / senior_mix)."""

from __future__ import annotations

from bugmiester.freshness import SEED_POOL, pick_seed
from bugmiester.mix import (
    BEGINNER_MIX_CATEGORIES,
    DEFAULT_MIX,
    SENIOR_CORE_CATEGORIES,
    SLOP_MIX_CATEGORIES,
    difficulty_label,
    is_gnarly_seed,
    normalize_mix,
    slop_quota,
)


def test_normalize_mix_defaults_unknown_to_senior() -> None:
    assert normalize_mix("senior_mix") == "senior_mix"
    assert normalize_mix("beginner_mix") == "beginner_mix"
    assert normalize_mix("intermediate_mix") == "intermediate_mix"
    assert normalize_mix("nope") == DEFAULT_MIX
    assert normalize_mix(None) == DEFAULT_MIX


def test_senior_mix_ramps_slop_then_senior_then_gnarly() -> None:
    used: set[str] = set()
    seeds = []
    for _ in range(10):
        seed = pick_seed(
            SEED_POOL,
            used,
            mix="senior_mix",
            bugs_per_round=10,
        )
        used.add(seed.seed_id)
        seeds.append(seed)
    quota = slop_quota(10)
    assert quota == 2
    assert all(seed.category in SLOP_MIX_CATEGORIES for seed in seeds[:quota])
    assert all(
        seed.category in SENIOR_CORE_CATEGORIES for seed in seeds[quota:-2]
    )
    assert all(is_gnarly_seed(seed) for seed in seeds[-2:])
    assert seeds[-2].seed_id == "conc-continuation-stuck"
    assert seeds[-1].seed_id == "actor-await-stale"
    assert len({seed.category for seed in seeds}) == 10
    assert [difficulty_label("senior_mix", i, 10) for i in range(10)] == [
        "Simple",
        "Simple",
        "Common",
        "Common",
        "Common",
        "Common",
        "Common",
        "Common",
        "Gnarly",
        "Gnarly",
    ]


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
    assert difficulty_label("intermediate_mix", 0, 10) == ""
    assert difficulty_label("beginner_mix", 8, 10) == ""
