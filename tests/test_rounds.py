"""Slice 05: mock round APIs."""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from bugmiester.app import create_app
from bugmiester.config import ensure_app_dir, load_settings


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


def test_full_mock_round_no_answer_key_leak(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        started = client.post("/api/round/start").json()
        assert started["bugs_per_round"] == 10
        assert started["round_score"] == 0
        round_id = started["round_id"]

        for i in range(10):
            bug = client.post(
                "/api/round/next-bug", json={"round_id": round_id}
            ).json()
            assert bug["index"] == i
            assert bug["mix"] == "senior_mix"
            assert bug["difficulty_label"] == [
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
            ][i]
            assert "bug_summary" not in bug
            assert "hints" not in bug
            assert "keywords" not in bug
            assert "bug_category" not in bug
            assert bug["code"]
            assert bug["snippet_id"]

            # Use a strong answer drawn from later reveal path: submit known good keywords.
            # Scoring is temporary keyword match; use words likely in summaries.
            answer = "force unwrap optional nil empty zero index count throws actor let mutate"
            result = client.post(
                "/api/round/submit",
                json={
                    "round_id": round_id,
                    "snippet_id": bug["snippet_id"],
                    "answer": answer,
                },
            ).json()
            if result.get("recovery_available"):
                for option in result.get("recovery_options") or []:
                    assert "correct" not in option
                    assert "id" in option and "text" in option
                result = client.post(
                    "/api/round/recover",
                    json={
                        "round_id": round_id,
                        "snippet_id": bug["snippet_id"],
                        "option_id": None,
                    },
                ).json()
            assert "expected_summary" in result
            assert result["index"] == i
            assert result["round_complete"] is (i == 9)

        assert result["round_complete"] is True
        assert result["summary"] is not None
        assert result["summary"]["round_possible"] == 100
        assert result["round_score"] >= 0

        summary = client.get(f"/api/round/{round_id}/summary").json()
        assert summary["round_possible"] == 100

        # No more bugs.
        blocked = client.post("/api/round/next-bug", json={"round_id": round_id})
        assert blocked.status_code == 400


def test_resume_round_after_ops_navigation(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        round_id = client.post("/api/round/start").json()["round_id"]
        empty = client.get(f"/api/round/{round_id}").json()
        assert empty["snippet_id"] is None
        assert empty["expected_summary"] == ""
        assert "bug_summary" not in empty

        bug = client.post(
            "/api/round/next-bug", json={"round_id": round_id}
        ).json()
        live = client.get(f"/api/round/{round_id}").json()
        assert live["snippet_id"] == bug["snippet_id"]
        assert live["code"] == bug["code"]
        assert live["answered"] is False
        assert live["expected_summary"] == ""
        assert live["feedback"] == ""
        assert "bug_summary" not in live
        assert "hints" not in live
        assert "keywords" not in live
        assert "bug_category" not in live

        submitted = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "answer": "css grid stylesheet overflow python gil deadlock",
            },
        ).json()
        if submitted.get("recovery_available"):
            restored = client.get(
                f"/api/round/{round_id}",
                params={"snippet_id": bug["snippet_id"]},
            ).json()
            assert restored["answered"] is True
            assert restored["recovery_available"] is True
            assert restored["expected_summary"] == ""
            assert restored["recovery_options"]
            for option in restored["recovery_options"]:
                assert "correct" not in option
            client.post(
                "/api/round/recover",
                json={
                    "round_id": round_id,
                    "snippet_id": bug["snippet_id"],
                    "option_id": None,
                },
            )

        scored = client.get(
            f"/api/round/{round_id}",
            params={"snippet_id": bug["snippet_id"]},
        ).json()
        assert scored["answered"] is True
        assert scored["expected_summary"]
        assert scored["player_answer"]
        assert "bug_summary" not in scored

        nxt = client.post(
            "/api/round/next-bug", json={"round_id": round_id}
        ).json()
        with_pending = client.get(
            f"/api/round/{round_id}",
            params={"snippet_id": bug["snippet_id"]},
        ).json()
        assert with_pending["snippet_id"] == bug["snippet_id"]
        assert with_pending["answered"] is True
        assert with_pending["pending"] is not None
        assert with_pending["pending"]["snippet_id"] == nxt["snippet_id"]
        assert "bug_summary" not in with_pending["pending"]

        missing = client.get("/api/round/not-a-round")
        assert missing.status_code == 404


def test_game_js_restores_round_from_session(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        js = client.get("/app.js").text
    assert "sessionStorage" in js
    assert "bugmiester.activeRound" in js
    assert "/api/round/" in js


def _play_mock_round(client: TestClient) -> list[str]:
    round_id = client.post("/api/round/start").json()["round_id"]
    codes: list[str] = []
    for _ in range(10):
        bug = client.post(
            "/api/round/next-bug", json={"round_id": round_id}
        ).json()
        codes.append(bug["code"])
        result = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "answer": "css grid stylesheet overflow python gil deadlock",
            },
        ).json()
        if result.get("recovery_available"):
            client.post(
                "/api/round/recover",
                json={
                    "round_id": round_id,
                    "snippet_id": bug["snippet_id"],
                    "option_id": None,
                },
            )
    return codes


def test_second_round_avoids_recent_seed_snippets(
    tmp_path: Path, monkeypatch
) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        first = _play_mock_round(client)
        second = _play_mock_round(client)
    assert len(first) == 10
    assert len(set(first)) == 10
    assert len(set(second)) == 10
    assert not set(first) & set(second)


def test_next_bug_rejects_openai_without_key(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    # Flip provider to openai with placeholder after settings object created —
    # reload from disk instead.
    app_dir = settings.app_dir
    raw = yaml.safe_load(settings.config_path.read_text(encoding="utf-8"))
    raw["llm"]["provider"] = "openai"
    settings.config_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    examples = tmp_path / "examples"
    monkeypatch.setattr("bugmiester.app.default_examples_dir", lambda: examples)
    fresh = load_settings(
        app_dir=app_dir, examples_dir=examples, load_env_into_process=False
    )
    app = create_app(settings=fresh)

    with TestClient(app) as client:
        round_id = client.post("/api/round/start").json()["round_id"]
        response = client.post("/api/round/next-bug", json={"round_id": round_id})
        assert response.status_code == 503
        assert "OPENAI_API_KEY" in response.json()["detail"]["message"]
