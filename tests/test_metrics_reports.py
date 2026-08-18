"""Slice 08: metrics logs + snippet reports."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from bugmiester.app import create_app
from bugmiester.config import ensure_app_dir, load_settings
from bugmiester.metrics import MetricsCollector
from bugmiester.reports import REPORT_REASONS, normalize_reason, write_report


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


def test_metrics_flush_writes_round_log(tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    collector = MetricsCollector()
    collector.start_round(
        "r1",
        bugs_per_round=2,
        provider="mock",
        model="fixture",
        round_possible=20,
    )
    collector.record_generate(
        "r1",
        snippet_id="s1",
        index=0,
        seed_id="opt-dict-force",
        generate_ms=12.5,
        generate_attempts=1,
        freshness_rejects=0,
        degraded=False,
        provider="mock",
        model="fixture",
    )
    collector.record_submit(
        "r1",
        "s1",
        submit_ms=3.0,
        judge_called=False,
        points_awarded=10,
        correct=True,
        partial=False,
        round_score=10,
    )
    path = collector.flush_round(logs, "r1", round_score=10)
    assert path is not None
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["round_id"] == "r1"
    assert payload["provider"] == "mock"
    assert payload["model"] == "fixture"
    assert payload["completed_at"]
    assert len(payload["bugs"]) == 1
    bug = payload["bugs"][0]
    assert bug["generate_attempts"] == 1
    assert bug["freshness_rejects"] == 0
    assert bug["judge_called"] is False
    assert bug["degraded"] is False
    assert bug["generate_ms"] == 12.5
    assert bug["submit_ms"] == 3.0


def test_write_report_creates_json(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    report_id, path = write_report(
        reports,
        round_id="r1",
        snippet_id="s1",
        reason="ambiguous",
        note="unclear",
        code="let x = 1",
        bug_summary="example bug",
        bug_category="optionals",
        player_answer="force unwrap",
        points_awarded=0,
        points_possible=10,
        correct=False,
        partial=False,
        provider="mock",
        model="fixture",
        degraded=False,
    )
    assert report_id
    assert path.is_file()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["reason"] == "ambiguous"
    assert payload["code"] == "let x = 1"
    assert payload["bug_summary"] == "example bug"
    assert payload["player_answer"] == "force unwrap"
    assert payload["provider"] == "mock"


def test_normalize_reason_rejects_unknown() -> None:
    for reason in REPORT_REASONS:
        assert normalize_reason(reason) == reason
    try:
        normalize_reason("not_a_reason")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_full_mock_round_writes_log_and_report(
    tmp_path: Path, monkeypatch
) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        round_id = client.post("/api/round/start").json()["round_id"]
        reported_snippet_id = None
        for i in range(10):
            bug = client.post(
                "/api/round/next-bug", json={"round_id": round_id}
            ).json()
            result = client.post(
                "/api/round/submit",
                json={
                    "round_id": round_id,
                    "snippet_id": bug["snippet_id"],
                    "answer": (
                        "force unwrap optional nil empty zero index count "
                        "throws actor let mutate switch default await"
                    ),
                },
            ).json()
            if result.get("recovery_available"):
                result = client.post(
                    "/api/round/recover",
                    json={
                        "round_id": round_id,
                        "snippet_id": bug["snippet_id"],
                        "option_id": None,
                    },
                ).json()
            if i == 0:
                reported_snippet_id = bug["snippet_id"]
                reported = client.post(
                    "/api/round/report-snippet",
                    json={
                        "round_id": round_id,
                        "snippet_id": bug["snippet_id"],
                        "reason": "ambiguous",
                        "note": "test report",
                    },
                )
                assert reported.status_code == 200
                assert reported.json() == {"ok": True}
            assert "expected_summary" in result

        assert result["round_complete"] is True

        log_path = settings.logs_dir / f"round_{round_id}.json"
        assert log_path.is_file()
        log_payload = json.loads(log_path.read_text(encoding="utf-8"))
        assert log_payload["round_id"] == round_id
        assert len(log_payload["bugs"]) == 10
        for bug in log_payload["bugs"]:
            assert "generate_ms" in bug
            assert "submit_ms" in bug
            assert "generate_attempts" in bug
            assert "freshness_rejects" in bug
            assert "judge_called" in bug
            assert "degraded" in bug
            assert bug["provider"] == "mock"
            assert bug["model"]

        report_files = list(settings.reports_dir.glob("report_*.json"))
        assert len(report_files) == 1
        report_payload = json.loads(report_files[0].read_text(encoding="utf-8"))
        assert report_payload["reason"] == "ambiguous"
        assert report_payload["snippet_id"] == reported_snippet_id
        assert report_payload["round_id"] == round_id
        assert report_payload["bug_summary"]
        assert report_payload["player_answer"]


def test_report_rejects_invalid_reason(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        round_id = client.post("/api/round/start").json()["round_id"]
        bug = client.post(
            "/api/round/next-bug", json={"round_id": round_id}
        ).json()
        client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "answer": "force unwrap optional nil",
            },
        )
        bad = client.post(
            "/api/round/report-snippet",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "reason": "not_valid",
                "note": "",
            },
        )
        assert bad.status_code == 400
