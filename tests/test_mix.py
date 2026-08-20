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
    assert len({seed.seed_id for seed in seeds[-2:]}) == 2
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


def test_senior_mix_simple_band_varies_across_rounds() -> None:
    """Simple openers pick randomly among slop seeds, not always pool[0]."""
    first_ids: set[str] = set()
    for _ in range(40):
        seed = pick_seed(
            SEED_POOL,
            set(),
            mix="senior_mix",
            bugs_per_round=10,
        )
        assert seed.category in SLOP_MIX_CATEGORIES
        first_ids.add(seed.seed_id)
    assert len(first_ids) >= 3


def test_senior_mix_gnarly_band_varies_across_rounds() -> None:
    """End-of-round gnarly picks randomly among gnarly seeds."""
    last_ids: set[str] = set()
    for _ in range(40):
        used: set[str] = set()
        # Burn Simple + Common slots so the next pick is gnarly.
        for _slot in range(8):
            seed = pick_seed(
                SEED_POOL,
                used,
                mix="senior_mix",
                bugs_per_round=10,
            )
            used.add(seed.seed_id)
        gnarly = pick_seed(
            SEED_POOL,
            used,
            mix="senior_mix",
            bugs_per_round=10,
        )
        assert is_gnarly_seed(gnarly)
        last_ids.add(gnarly.seed_id)
    assert len(last_ids) >= 2


def test_senior_mix_ordinary_concurrency_in_common_not_gnarly_only() -> None:
    """Missing-await etc. can appear in Common; stuck continuation stays gnarly."""
    assert "concurrency" in SENIOR_CORE_CATEGORIES
    common_conc: set[str] = set()
    for _ in range(80):
        used: set[str] = set()
        for _slot in range(2):  # burn Simple
            used.add(
                pick_seed(
                    SEED_POOL, used, mix="senior_mix", bugs_per_round=10
                ).seed_id
            )
        seed = pick_seed(SEED_POOL, used, mix="senior_mix", bugs_per_round=10)
        assert not is_gnarly_seed(seed)
        if seed.category == "concurrency":
            common_conc.add(seed.seed_id)
    assert common_conc
    assert "conc-continuation-stuck" not in common_conc
    assert "conc-continuation-double" not in common_conc


def test_new_gnarly_allowlist_seeds_are_is_gnarly() -> None:
    by_id = {seed.seed_id: seed for seed in SEED_POOL}
    assert is_gnarly_seed(by_id["conc-continuation-double"])
    assert is_gnarly_seed(by_id["main-await-hop"])
    assert by_id["main-await-hop"].category == "MainActor"
