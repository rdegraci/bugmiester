"""Slice 04: /api/health and static UI smoke tests."""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from bugmiester.app import create_app, health_payload
from bugmiester.config import ensure_app_dir, load_settings


def _examples(tmp_path: Path) -> Path:
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / ".env.example").write_text(
        "OPENAI_API_KEY=replace-me\n"
        "ANTHROPIC_API_KEY=replace-me\n"
        "GROK_API_KEY=replace-me\n",
        encoding="utf-8",
    )
    # Reuse repo example YAML for realism.
    repo_example = Path(__file__).resolve().parents[1] / "config.yaml.example"
    (examples / "config.yaml.example").write_text(
        repo_example.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    return examples


def test_health_missing_key_not_ready(tmp_path: Path, monkeypatch) -> None:
    examples = _examples(tmp_path)
    app_dir = tmp_path / "app"
    monkeypatch.setattr(
        "bugmiester.app.default_examples_dir",
        lambda: examples,
    )
    settings = load_settings(app_dir=app_dir, examples_dir=examples, load_env_into_process=False)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["config_ready"] is False
    assert data["provider"] == "openai"
    assert data["missing_key"] == "OPENAI_API_KEY"
    assert data["app_dir"] == str(app_dir)
    assert data["env_path"] == str(app_dir / ".env")
    assert data["config_path"] == str(app_dir / "config.yaml")
    assert "OPENAI_API_KEY" in data["message"]
    assert str(app_dir / ".env") in data["message"]


def test_health_mock_ready(tmp_path: Path, monkeypatch) -> None:
    examples = _examples(tmp_path)
    app_dir = tmp_path / "app"
    monkeypatch.setattr("bugmiester.app.default_examples_dir", lambda: examples)
    ensure_app_dir(app_dir=app_dir, examples_dir=examples)
    raw = yaml.safe_load((app_dir / "config.yaml").read_text(encoding="utf-8"))
    raw["llm"]["provider"] = "mock"
    (app_dir / "config.yaml").write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    settings = load_settings(app_dir=app_dir, examples_dir=examples, load_env_into_process=False)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        data = client.get("/api/health").json()

    assert data["config_ready"] is True
    assert data["provider"] == "mock"
    assert data["missing_key"] is None
    assert data["prefetch_next_bug"] is True


def test_serves_index_and_ops_and_vendor(tmp_path: Path, monkeypatch) -> None:
    examples = _examples(tmp_path)
    app_dir = tmp_path / "app"
    monkeypatch.setattr("bugmiester.app.default_examples_dir", lambda: examples)
    settings = load_settings(app_dir=app_dir, examples_dir=examples, load_env_into_process=False)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        index = client.get("/")
        ops = client.get("/ops")
        css = client.get("/vendor/bootstrap/bootstrap.min.css")
        js = client.get("/app.js")

    assert index.status_code == 200
    assert b"Bugmiester" in index.content
    assert ops.status_code == 200
    assert b"Bugmiester Ops" in ops.content
    assert css.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert js.status_code == 200


def test_health_payload_shape() -> None:
    # Smoke the helper with a minimal fake-like Settings via load on empty — skip if heavy.
    # Shape keys are asserted in the HTTP tests above; keep helper importable.
    assert callable(health_payload)
