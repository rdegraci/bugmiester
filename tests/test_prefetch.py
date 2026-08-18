"""Slice 14: prefetch_next_bug resilience + health flag."""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from bugmiester.app import create_app
from bugmiester.config import ensure_app_dir, load_settings


def _mock_settings(tmp_path: Path, monkeypatch, *, prefetch: bool = True):
    examples = tmp_path / "examples"
    examples.mkdir(parents=True)
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
    raw.setdefault("resilience", {})
    raw["resilience"]["prefetch_next_bug"] = prefetch
    (app_dir / "config.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )
    monkeypatch.setattr("bugmiester.app.default_examples_dir", lambda: examples)
    return load_settings(
        app_dir=app_dir, examples_dir=examples, load_env_into_process=False
    )


def test_health_exposes_prefetch_flag(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path / "on", monkeypatch, prefetch=True)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        data = client.get("/api/health").json()
    assert data["prefetch_next_bug"] is True

    settings_off = _mock_settings(tmp_path / "off", monkeypatch, prefetch=False)
    app_off = create_app(settings=settings_off)
    with TestClient(app_off) as client:
        assert client.get("/api/health").json()["prefetch_next_bug"] is False


def test_prefetch_style_next_after_submit_no_double_advance(
    tmp_path: Path, monkeypatch
) -> None:
    """Simulate UI prefetch: submit → next-bug once → pending blocks a second next."""
    settings = _mock_settings(tmp_path, monkeypatch, prefetch=True)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        round_id = client.post("/api/round/start").json()["round_id"]
        first = client.post(
            "/api/round/next-bug", json={"round_id": round_id}
        ).json()
        assert first["index"] == 0

        submit = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": first["snippet_id"],
                "answer": "force unwrap optional nil empty",
            },
        ).json()
        assert submit["round_complete"] is False
        assert submit["index"] == 0

        # Prefetch / Next: one generate for index 1.
        prefetched = client.post(
            "/api/round/next-bug", json={"round_id": round_id}
        ).json()
        assert prefetched["index"] == 1
        assert prefetched["snippet_id"] != first["snippet_id"]
        assert "bug_summary" not in prefetched

        # A duplicate Next (race) must not skip ahead — pending unanswered blocks it.
        blocked = client.post(
            "/api/round/next-bug", json={"round_id": round_id}
        )
        assert blocked.status_code == 400
        assert blocked.json()["detail"]["code"] == "pending_answer"

        # Completing the prefetched bug advances to index 2 normally.
        second_submit = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": prefetched["snippet_id"],
                "answer": "force unwrap optional nil empty zero",
            },
        ).json()
        assert second_submit["index"] == 1

        third = client.post(
            "/api/round/next-bug", json={"round_id": round_id}
        ).json()
        assert third["index"] == 2


def test_app_js_contains_prefetch_hooks(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        js = client.get("/app.js")
    assert js.status_code == 200
    text = js.text
    assert "startPrefetch" in text
    assert "takePrefetchedOrFetch" in text
    assert "Preparing bug" in text
    assert "prefetch_next_bug" in text
    assert "502" in text and "503" in text
