"""Unit tests for Application Support config bootstrap and key resolution."""

from __future__ import annotations

from pathlib import Path

import yaml

from bugmiester.config import (
    PLACEHOLDER_KEY,
    ensure_app_dir,
    load_settings,
    resolve_provider_key,
)


def _write_examples(examples: Path) -> None:
    examples.mkdir(parents=True, exist_ok=True)
    (examples / ".env.example").write_text(
        "OPENAI_API_KEY=replace-me\n"
        "ANTHROPIC_API_KEY=replace-me\n"
        "XAI_API_KEY=replace-me\n",
        encoding="utf-8",
    )
    config = {
        "llm": {
            "provider": "openai",
            "base_url": None,
            "model": "gpt-4o-mini",
            "temperature": 0.4,
            "judge_temperature": 0.0,
            "timeout_seconds": 60,
        },
        "game": {"bugs_per_round": 10, "language": "swift"},
        "scoring": {
            "mode": "hybrid",
            "points_per_bug": 10,
            "partial_credit": True,
            "generosity": "prefer_partial_on_low_confidence",
        },
        "freshness": {
            "avoid_list_max": 20,
            "similarity_reject_threshold": 0.72,
            "max_generate_attempts": 2,
        },
        "resilience": {
            "max_judge_calls_per_submit": 1,
            "use_canned_fallback_on_generate_exhaustion": True,
            "prefetch_next_bug": True,
        },
        "metrics": {"log_per_bug": True, "log_dir_name": "logs"},
        "reports": {"enabled": True, "dir_name": "reports"},
        "feedback": {"analyze_on_ops_load": True},
        "server": {"host": "127.0.0.1", "port": 8765},
    }
    (examples / "config.yaml.example").write_text(
        yaml.safe_dump(config, sort_keys=False),
        encoding="utf-8",
    )


def test_ensure_app_dir_copies_examples_and_creates_subdirs(tmp_path: Path) -> None:
    examples = tmp_path / "examples"
    app_dir = tmp_path / "app"
    _write_examples(examples)

    root = ensure_app_dir(app_dir=app_dir, examples_dir=examples)

    assert root == app_dir
    assert (app_dir / ".env").is_file()
    assert (app_dir / "config.yaml").is_file()
    assert (app_dir / "reports").is_dir()
    assert (app_dir / "logs").is_dir()
    assert "OPENAI_API_KEY=replace-me" in (app_dir / ".env").read_text(encoding="utf-8")


def test_ensure_app_dir_does_not_overwrite_existing(tmp_path: Path) -> None:
    examples = tmp_path / "examples"
    app_dir = tmp_path / "app"
    _write_examples(examples)
    app_dir.mkdir(parents=True)
    (app_dir / ".env").write_text("OPENAI_API_KEY=keep-me\n", encoding="utf-8")
    (app_dir / "config.yaml").write_text("llm:\n  provider: mock\n", encoding="utf-8")

    ensure_app_dir(app_dir=app_dir, examples_dir=examples)

    assert (app_dir / ".env").read_text(encoding="utf-8") == "OPENAI_API_KEY=keep-me\n"
    assert "provider: mock" in (app_dir / "config.yaml").read_text(encoding="utf-8")


def test_load_settings_placeholder_not_ready(tmp_path: Path) -> None:
    examples = tmp_path / "examples"
    app_dir = tmp_path / "app"
    _write_examples(examples)

    settings = load_settings(
        app_dir=app_dir,
        examples_dir=examples,
        load_env_into_process=False,
    )

    assert settings.app_dir == app_dir
    assert settings.env_path == app_dir / ".env"
    assert settings.config_path == app_dir / "config.yaml"
    assert settings.llm.provider == "openai"
    assert settings.config_ready is False
    assert settings.missing_key == "OPENAI_API_KEY"
    assert settings.api_key is None


def test_load_settings_real_key_ready(tmp_path: Path) -> None:
    examples = tmp_path / "examples"
    app_dir = tmp_path / "app"
    _write_examples(examples)
    ensure_app_dir(app_dir=app_dir, examples_dir=examples)
    (app_dir / ".env").write_text(
        "OPENAI_API_KEY=sk-test-real\n"
        "ANTHROPIC_API_KEY=replace-me\n"
        "XAI_API_KEY=replace-me\n",
        encoding="utf-8",
    )

    settings = load_settings(
        app_dir=app_dir,
        examples_dir=examples,
        load_env_into_process=False,
    )

    assert settings.config_ready is True
    assert settings.missing_key is None
    assert settings.api_key == "sk-test-real"


def test_load_settings_mock_always_ready(tmp_path: Path) -> None:
    examples = tmp_path / "examples"
    app_dir = tmp_path / "app"
    _write_examples(examples)
    ensure_app_dir(app_dir=app_dir, examples_dir=examples)

    raw = yaml.safe_load((app_dir / "config.yaml").read_text(encoding="utf-8"))
    raw["llm"]["provider"] = "mock"
    (app_dir / "config.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False),
        encoding="utf-8",
    )

    settings = load_settings(
        app_dir=app_dir,
        examples_dir=examples,
        load_env_into_process=False,
    )

    assert settings.llm.provider == "mock"
    assert settings.config_ready is True
    assert settings.missing_key is None
    assert settings.api_key is None
    assert settings.recovery.enabled is True
    assert settings.recovery.choice_count == 4
    assert settings.recovery.timeout_seconds == 4
    assert settings.recovery.max_llm_calls == 1
    assert settings.recovery.use_seed_bank_fallback is True
    assert settings.freshness.shuffle_seeds is True
    assert settings.freshness.max_category_repeats_per_round == 1
    assert settings.freshness.recent_seed_rounds == 3


def test_resolve_provider_key_helpers() -> None:
    assert resolve_provider_key("mock") == (None, None, True)
    assert resolve_provider_key(
        "openai", {"OPENAI_API_KEY": PLACEHOLDER_KEY}
    ) == (None, "OPENAI_API_KEY", False)
    assert resolve_provider_key(
        "anthropic", {"ANTHROPIC_API_KEY": "claude-key"}
    ) == ("claude-key", None, True)
    assert resolve_provider_key(
        "xai", {"XAI_API_KEY": "xai-key"}
    ) == ("xai-key", None, True)
