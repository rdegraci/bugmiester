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
