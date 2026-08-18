"""Slice 12: Anthropic provider (mocked Messages API)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import yaml
from fastapi.testclient import TestClient

from bugmiester.app import create_app
from bugmiester.config import ensure_app_dir, load_settings
from bugmiester.llm import generate_bug
from bugmiester.llm.anthropic_provider import (
    AnthropicConfigError,
    generate_raw,
    judge_raw,
)


def _settings_with_anthropic(
    tmp_path: Path, monkeypatch, *, api_key: str = "sk-ant-test"
):
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
    (app_dir / ".env").write_text(f"ANTHROPIC_API_KEY={api_key}\n", encoding="utf-8")
    raw = yaml.safe_load((app_dir / "config.yaml").read_text(encoding="utf-8"))
    raw["llm"]["provider"] = "anthropic"
    raw["llm"]["model"] = "claude-3-5-haiku-latest"
    raw["llm"]["base_url"] = None
    (app_dir / "config.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )
    monkeypatch.setattr("bugmiester.app.default_examples_dir", lambda: examples)
    return load_settings(
        app_dir=app_dir, examples_dir=examples, load_env_into_process=False
    )


def _tool_response(tool_name: str, payload: dict) -> SimpleNamespace:
    block = SimpleNamespace(type="tool_use", name=tool_name, input=payload)
    return SimpleNamespace(content=[block])


def test_generate_raw_missing_key_raises(tmp_path: Path, monkeypatch) -> None:
    settings = _settings_with_anthropic(tmp_path, monkeypatch, api_key="replace-me")
    assert settings.config_ready is False
    with pytest.raises(AnthropicConfigError, match="ANTHROPIC_API_KEY"):
        generate_raw("prompt", settings)


def test_generate_and_judge_use_tool_json(tmp_path: Path, monkeypatch) -> None:
    settings = _settings_with_anthropic(tmp_path, monkeypatch)
    assert settings.config_ready is True

    gen_payload = {
        "code": "func x() { return y! }",
        "bug_summary": "Force unwrap of y",
        "bug_category": "optionals",
        "difficulty": "beginner",
        "hints": ["!"],
        "keywords": ["force unwrap"],
    }
    judge_payload = {
        "correct": True,
        "partial": False,
        "feedback": "Yes.",
        "confidence": 0.9,
    }

    create_mock = MagicMock()
    create_mock.side_effect = [
        _tool_response("bugmiester_generation", gen_payload),
        _tool_response("bugmiester_judge", judge_payload),
    ]
    client = MagicMock()
    client.messages.create = create_mock
    monkeypatch.setattr(
        "bugmiester.llm.anthropic_provider._build_client",
        lambda _settings: client,
    )

    raw = generate_raw("gen prompt", settings)
    assert json.loads(raw)["bug_summary"] == "Force unwrap of y"
    first_kwargs = create_mock.call_args_list[0].kwargs
    assert first_kwargs["model"] == "claude-3-5-haiku-latest"
    assert first_kwargs["temperature"] == settings.llm.temperature
    assert first_kwargs["tool_choice"]["name"] == "bugmiester_generation"
    assert first_kwargs["tools"][0]["input_schema"]["required"]

    raw_judge = judge_raw("judge prompt", settings)
    assert json.loads(raw_judge)["correct"] is True
    second_kwargs = create_mock.call_args_list[1].kwargs
    assert second_kwargs["temperature"] == settings.llm.judge_temperature
    assert second_kwargs["tool_choice"]["name"] == "bugmiester_judge"


def test_facade_anthropic_generate_bug(tmp_path: Path, monkeypatch) -> None:
    settings = _settings_with_anthropic(tmp_path, monkeypatch)
    gen_payload = {
        "code": "let a = b!",
        "bug_summary": "Force unwrap of optional b",
        "bug_category": "optionals",
        "difficulty": "beginner",
        "hints": ["optional"],
        "keywords": ["force unwrap", "optional"],
    }
    client = MagicMock()
    client.messages.create = MagicMock(
        return_value=_tool_response("bugmiester_generation", gen_payload)
    )
    monkeypatch.setattr(
        "bugmiester.llm.anthropic_provider._build_client",
        lambda _settings: client,
    )

    outcome = generate_bug(settings, used_seed_ids=set(), history=[])
    assert outcome.snippet.code == gen_payload["code"]
    assert outcome.degraded is False


def test_round_api_anthropic_mocked_no_key_leak(tmp_path: Path, monkeypatch) -> None:
    settings = _settings_with_anthropic(tmp_path, monkeypatch)
    payloads = [
        {
            "code": 'func firstName(from dict: [String: String]) -> String { return dict["name"]! }',
            "bug_summary": "Force unwrap of a dictionary value that may be nil",
            "bug_category": "optionals",
            "difficulty": "beginner",
            "hints": ["!"],
            "keywords": ["force unwrap", "nil"],
        },
        {
            "code": "func average(_ values: [Int]) -> Int { return values.reduce(0, +) / values.count }",
            "bug_summary": "Division by zero when the array is empty",
            "bug_category": "collections",
            "difficulty": "beginner",
            "hints": ["empty"],
            "keywords": ["division by zero", "empty"],
        },
        {
            "code": "let origin = Point(x: 0, y: 0)\norigin.x = 1",
            "bug_summary": "Cannot mutate a let struct value",
            "bug_category": "value vs reference",
            "difficulty": "beginner",
            "hints": ["let"],
            "keywords": ["let", "mutate", "struct"],
        },
    ]
    judge = _tool_response(
        "bugmiester_judge",
        {
            "correct": True,
            "partial": False,
            "feedback": "Yes.",
            "confidence": 0.95,
        },
    )
    # Extra generate fixtures cover possible freshness retries.
    create_mock = MagicMock(
        side_effect=[_tool_response("bugmiester_generation", p) for p in payloads] * 2
        + [judge] * 6
    )
    client = MagicMock()
    client.messages.create = create_mock
    monkeypatch.setattr(
        "bugmiester.llm.anthropic_provider._build_client",
        lambda _settings: client,
    )

    app = create_app(settings=settings)
    with TestClient(app) as http:
        round_id = http.post("/api/round/start").json()["round_id"]
        for _ in range(3):
            response = http.post(
                "/api/round/next-bug", json={"round_id": round_id}
            )
            assert response.status_code == 200, response.text
            bug = response.json()
            assert "bug_summary" not in bug
            assert "hints" not in bug
            assert "keywords" not in bug
            assert bug["code"]
            result = http.post(
                "/api/round/submit",
                json={
                    "round_id": round_id,
                    "snippet_id": bug["snippet_id"],
                    "answer": "force unwrap nil optional empty division let mutate",
                },
            ).json()
            if result.get("recovery_available"):
                assert result["expected_summary"] == ""
                assert result["recovery_options"]
            else:
                assert result["expected_summary"]
            assert result["points_possible"] == 10


def test_round_anthropic_missing_key_503(tmp_path: Path, monkeypatch) -> None:
    settings = _settings_with_anthropic(tmp_path, monkeypatch, api_key="replace-me")
    app = create_app(settings=settings)
    with TestClient(app) as http:
        round_id = http.post("/api/round/start").json()["round_id"]
        response = http.post("/api/round/next-bug", json={"round_id": round_id})
        assert response.status_code == 503
        assert "ANTHROPIC_API_KEY" in response.json()["detail"]["message"]
