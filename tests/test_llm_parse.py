"""Slice 10: LLM parse + facade attempt accounting."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from bugmiester.app import create_app
from bugmiester.config import ensure_app_dir, load_settings
from bugmiester.fallback_snippets import fallback_for_seed
from bugmiester.freshness import SEED_POOL, generate_with_freshness
from bugmiester.llm import generate_bug, judge_answer
from bugmiester.llm.base import JudgeResult, SnippetWithKey
from bugmiester.llm.mock_provider import MockProvider
from bugmiester.llm.parse import ParseError, parse_generation_payload, parse_judge_payload
from bugmiester.llm.prompts import build_generation_prompt, build_judge_prompt


def test_parse_generation_requires_keys() -> None:
    with pytest.raises(ParseError, match="Missing required keys"):
        parse_generation_payload({"code": "func x() {}"})


def test_parse_generation_happy_path() -> None:
    snippet = parse_generation_payload(
        {
            "code": "func x() { return y! }",
            "bug_summary": "Force unwrap of y",
            "bug_category": "optionals",
            "difficulty": "beginner",
            "hints": ["Look at !"],
            "keywords": ["force unwrap", "nil"],
        }
    )
    assert isinstance(snippet, SnippetWithKey)
    assert snippet.difficulty == "beginner"
    assert snippet.keywords == ("force unwrap", "nil")


def test_parse_generation_rejects_invalid_json() -> None:
    with pytest.raises(ParseError, match="Invalid JSON"):
        parse_generation_payload("not-json{")


def test_parse_judge_payload() -> None:
    judged = parse_judge_payload(
        {
            "correct": False,
            "partial": True,
            "feedback": "Close.",
            "confidence": 0.4,
        }
    )
    assert isinstance(judged, JudgeResult)
    assert judged.partial is True
    assert judged.confidence == 0.4


def test_prompts_include_seed_and_avoid_list() -> None:
    seed = SEED_POOL[0]
    avoid = []
    prompt = build_generation_prompt(seed, avoid)
    assert "Exactly ONE intentional bug" in prompt
    assert "failure mode" in prompt
    assert seed.seed_id in prompt
    assert "bug_summary" in prompt

    judge_prompt = build_judge_prompt(
        code="let x = y!",
        expected_summary="Force unwrap",
        player_answer="force unwrap",
    )
    assert "Force unwrap" in judge_prompt
    assert "force unwrap" in judge_prompt
    assert "confidence" in judge_prompt


def test_invalid_mock_json_consumes_shared_attempts() -> None:
    seed = SEED_POOL[0]
    provider = MockProvider(
        invalid_raw_queue=[
            "not-json",
            '{"code":"x"}',  # missing required keys
        ]
    )
    used: set[str] = set()

    def generate_raw_fn(_seed, _avoid) -> str:
        return provider.generate_raw("seed_id: " + seed.seed_id, seed=seed)

    def parse_raw(raw: str):
        snippet = parse_generation_payload(raw)
        from bugmiester.freshness import GeneratedSnippet

        return GeneratedSnippet(
            code=snippet.code,
            bug_summary=snippet.bug_summary,
            bug_category=snippet.bug_category,
            difficulty=snippet.difficulty,
            hints=snippet.hints,
            keywords=snippet.keywords,
            seed=seed,
        )

    result, degraded, attempts, rejects, parse_failures = generate_with_freshness(
        used_seed_ids=used,
        history=[],
        seed_pool=(seed,),
        max_attempts=2,
        use_fallback=True,
        generate_raw_fn=generate_raw_fn,
        parse_raw=parse_raw,
        fallback_fn=fallback_for_seed,
    )
    assert degraded is True
    assert attempts == 2
    assert parse_failures == 2
    assert rejects == 0
    assert result.seed.seed_id == seed.seed_id


def test_one_invalid_then_valid_counts_parse_failure_once() -> None:
    seed = SEED_POOL[0]
    good = MockProvider().generate_raw("", seed=seed)
    provider = MockProvider(invalid_raw_queue=["{{{", good])
    used: set[str] = set()

    def generate_raw_fn(_seed, _avoid) -> str:
        return provider.generate_raw("x", seed=seed)

    def parse_raw(raw: str):
        snippet = parse_generation_payload(raw)
        from bugmiester.freshness import GeneratedSnippet

        return GeneratedSnippet(
            code=snippet.code,
            bug_summary=snippet.bug_summary,
            bug_category=snippet.bug_category,
            difficulty=snippet.difficulty,
            hints=snippet.hints,
            keywords=snippet.keywords,
            seed=seed,
        )

    result, degraded, attempts, rejects, parse_failures = generate_with_freshness(
        used_seed_ids=used,
        history=[],
        seed_pool=(seed,),
        max_attempts=2,
        use_fallback=True,
        generate_raw_fn=generate_raw_fn,
        parse_raw=parse_raw,
        fallback_fn=fallback_for_seed,
    )
    assert degraded is False
    assert attempts == 2
    assert parse_failures == 1
    assert rejects == 0
    assert "!" in result.code or "dict" in result.code


def _mock_settings(tmp_path: Path, monkeypatch):
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / ".env.example").write_text(
        "OPENAI_API_KEY=replace-me\nANTHROPIC_API_KEY=replace-me\nGROK_API_KEY=replace-me\n",
        encoding="utf-8",
    )
    repo_example = Path(__file__).resolve().parents[1] / "config.yaml.example"
    (examples / "config.yaml.example").write_text(
        repo_example.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    app_dir = tmp_path / "app"
    ensure_app_dir(app_dir=app_dir, examples_dir=examples)
    raw = yaml.safe_load((app_dir / "config.yaml").read_text(encoding="utf-8"))
    raw["llm"]["provider"] = "mock"
    (app_dir / "config.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )
    monkeypatch.setattr("bugmiester.app.default_examples_dir", lambda: examples)
    return load_settings(
        app_dir=app_dir, examples_dir=examples, load_env_into_process=False
    )


def test_facade_mock_round_still_works(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    used: set[str] = set()
    outcome = generate_bug(settings, used_seed_ids=used, history=[])
    assert outcome.degraded is False
    assert outcome.attempts >= 1
    assert outcome.snippet.code
    assert outcome.snippet.bug_summary
    assert outcome.seed.seed_id in used

    judged = judge_answer(
        outcome.snippet.code,
        outcome.snippet.bug_summary,
        "force unwrap optional nil empty zero index",
        settings,
    )
    assert isinstance(judged, JudgeResult)

    app = create_app(settings=settings)
    with TestClient(app) as client:
        round_id = client.post("/api/round/start").json()["round_id"]
        bug = client.post("/api/round/next-bug", json={"round_id": round_id}).json()
        assert bug["code"]
        result = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "answer": "force unwrap optional nil dictionary",
            },
        ).json()
        if result.get("recovery_available"):
            assert result["expected_summary"] == ""
            assert result["recovery_options"]
        else:
            assert result["expected_summary"]
        assert result["points_possible"] == 10


def test_all_live_providers_need_keys(tmp_path: Path, monkeypatch) -> None:
    from dataclasses import replace

    settings = _mock_settings(tmp_path, monkeypatch)

    openai_settings = replace(settings, llm=replace(settings.llm, provider="openai"))
    from bugmiester.llm.openai_provider import OpenAIConfigError

    with pytest.raises(OpenAIConfigError):
        generate_bug(openai_settings, used_seed_ids=set(), history=[])

    anthropic_settings = replace(
        settings, llm=replace(settings.llm, provider="anthropic")
    )
    from bugmiester.llm.anthropic_provider import AnthropicConfigError

    with pytest.raises(AnthropicConfigError):
        generate_bug(anthropic_settings, used_seed_ids=set(), history=[])

    grok_settings = replace(settings, llm=replace(settings.llm, provider="grok"))
    from bugmiester.llm.grok_provider import GrokConfigError

    with pytest.raises(GrokConfigError):
        generate_bug(grok_settings, used_seed_ids=set(), history=[])
