"""Freshness similarity + degraded fallback tests."""

from __future__ import annotations

from bugmiester.fallback_snippets import fallback_for_seed
from bugmiester.freshness import (
    SEED_POOL,
    GeneratedSnippet,
    ScenarioSeed,
    generate_with_freshness,
    history_entry,
    is_too_similar,
    normalize_code,
    order_seed_pool,
    pick_seed,
    similarity_score,
)


def test_normalize_strips_comments_and_whitespace() -> None:
    code = """
    // note
    func a() {  /* x */  return 1
    }
    """
    assert "note" not in normalize_code(code)
    assert "func a() { return 1 }" == normalize_code(code)


def test_similarity_reject_identical_code() -> None:
    code = 'func x() { return y! }'
    summary = "Force unwrap of y"
    history = [
        history_entry(
            bug_summary=summary,
            bug_category="optionals",
            theme="optionals: test",
            code=code,
        )
    ]
    assert is_too_similar(code, summary, history, threshold=0.72) is True
    assert (
        is_too_similar(
            'struct Z { var a = 1 }',
            "Unrelated immutable issue",
            history,
            threshold=0.72,
        )
        is False
    )


def test_similarity_score_high_for_near_duplicates() -> None:
    a = "func firstName(from dict: [String: String]) -> String { return dict[\"name\"]! }"
    b = "func firstName(from dict: [String: String]) -> String {\n  return dict[\"name\"]!\n}"
    score = similarity_score(a, "Force unwrap nil", b, "Force unwrap of nil optional")
    assert score >= 0.72


def test_attempt_cap_surfaces_degraded_fallback() -> None:
    seed = SEED_POOL[0]
    duplicate = GeneratedSnippet(
        code="func same() { return x! }",
        bug_summary="Force unwrap of x",
        bug_category="optionals",
        difficulty="beginner",
        hints=("!",),
        keywords=("force unwrap",),
        seed=seed,
    )
    history = [
        history_entry(
            bug_summary=duplicate.bug_summary,
            bug_category=duplicate.bug_category,
            theme=seed.theme,
            code=duplicate.code,
        )
    ]

    def always_duplicate(
        _seed: ScenarioSeed, _avoid: object
    ) -> GeneratedSnippet:
        return duplicate

    used: set[str] = set()
    result, degraded, attempts, rejects, parse_failures = generate_with_freshness(
        used_seed_ids=used,
        history=history,
        seed_pool=(seed,),
        max_attempts=2,
        similarity_threshold=0.72,
        avoid_list_max=20,
        use_fallback=True,
        generate_fn=always_duplicate,
        fallback_fn=fallback_for_seed,
    )

    assert degraded is True
    assert attempts == 2
    assert rejects == 2
    assert parse_failures == 0
    assert result.code != duplicate.code
    assert "as!" in result.code or "first" in result.code or "max" in result.code
    assert seed.seed_id in used


def test_fresh_generate_accepts_unique_mock(monkeypatch) -> None:
    from bugmiester.llm.mock_provider import MockProvider

    provider = MockProvider()
    used: set[str] = set()
    result, degraded, attempts, rejects, parse_failures = generate_with_freshness(
        used_seed_ids=used,
        history=[],
        max_attempts=2,
        use_fallback=True,
        generate_fn=provider.generate_for_seed,
        fallback_fn=fallback_for_seed,
    )
    assert degraded is False
    assert attempts == 1
    assert rejects == 0
    assert parse_failures == 0
    assert result.code
    assert result.seed.seed_id in used


def test_pick_seed_uses_new_category_before_repeat() -> None:
    used: set[str] = set()
    seen_categories: list[str] = []
    unique_count = len({seed.category for seed in SEED_POOL})
    for _ in range(unique_count):
        seed = pick_seed(SEED_POOL, used, max_category_repeats=1)
        used.add(seed.seed_id)
        seen_categories.append(seed.category)
    assert len(seen_categories) == len(set(seen_categories))

    extra = pick_seed(SEED_POOL, used, max_category_repeats=1)
    assert extra.seed_id not in used
    assert extra.category in seen_categories


def test_order_seed_pool_shuffle_changes_order() -> None:
    import random

    random.seed(1)
    shuffled = order_seed_pool(SEED_POOL, shuffle=True)
    random.seed(1)
    shuffled_again = order_seed_pool(SEED_POOL, shuffle=True)
    frozen = order_seed_pool(SEED_POOL, shuffle=False)
    assert shuffled == shuffled_again
    assert frozen == SEED_POOL
    assert {s.seed_id for s in shuffled} == {s.seed_id for s in SEED_POOL}


def test_seed_pool_has_thirty_two_categories_wired_to_mock_and_fallback() -> None:
    from bugmiester.fallback_snippets import fallback_for_seed
    from bugmiester.llm.mock_provider import SEED_SNIPPETS

    categories = {seed.category for seed in SEED_POOL}
    assert categories >= {
        "optionals",
        "collections",
        "value vs reference",
        "control flow",
        "errors",
        "concurrency",
        "access control",
        "SwiftUI state",
        "captures",
        "equality",
        "sendable",
        "codable",
        "string indexes",
        "lazy",
        "protocol witnesses",
        "result",
        "type casting",
        "failable init",
        "inout / COW",
        "enums",
        "defer",
        "unowned",
        "some vs any",
        "autoclosure",
        "default arguments",
        "MainActor",
        "Task cancellation",
        "actor reentrancy",
        "SwiftUI environment",
        "Sequence slices",
        "Combine",
        "exclusivity",
    }
    assert len(categories) == 32
    assert len(SEED_POOL) == 80
    for seed in SEED_POOL:
        assert seed.seed_id in SEED_SNIPPETS
        mock = SEED_SNIPPETS[seed.seed_id]
        assert mock.bug_category == seed.category
        fallback = fallback_for_seed(seed)
        assert fallback.bug_category == seed.category
        assert fallback.code != mock.code
        assert fallback.bug_summary != mock.bug_summary


def test_order_seed_pool_puts_recent_seeds_last() -> None:
    recent = [seed.seed_id for seed in SEED_POOL[:10]]
    ordered = order_seed_pool(SEED_POOL, shuffle=False, recent_seed_ids=recent)
    unused_ids = [seed.seed_id for seed in SEED_POOL[10:]]
    assert [seed.seed_id for seed in ordered[: len(unused_ids)]] == unused_ids
    assert [seed.seed_id for seed in ordered[len(unused_ids) :]] == recent

    used: set[str] = set()
    picked: list[str] = []
    for _ in range(10):
        seed = pick_seed(ordered, used, max_category_repeats=1)
        used.add(seed.seed_id)
        picked.append(seed.seed_id)
    assert not set(picked) & set(recent)
