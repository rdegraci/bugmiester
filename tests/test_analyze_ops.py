"""Slice 09: analyze engine + ops API + CLI."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from bugmiester.analyze import ANALYZE_LATEST_NAME, analyze
from bugmiester.app import create_app
from bugmiester.config import ensure_app_dir, load_settings
from bugmiester.metrics import MetricsCollector
from bugmiester.reports import write_report


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


def test_analyze_aggregates_fixture_reports_and_logs(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    logs = tmp_path / "logs"
    reports.mkdir()
    logs.mkdir()

    write_report(
        reports,
        round_id="r1",
        snippet_id="s1",
        reason="duplicate",
        code="x",
        bug_summary="dup",
        bug_category="collections",
        seed_id="col-empty-avg",
        player_answer="empty",
        provider="mock",
        model="m",
    )
    write_report(
        reports,
        round_id="r1",
        snippet_id="s2",
        reason="ambiguous",
        code="y",
        bug_summary="amb",
        bug_category="optionals",
        seed_id="opt-dict-force",
        player_answer="?",
        provider="mock",
        model="m",
    )

    collector = MetricsCollector()
    collector.start_round(
        "r1", bugs_per_round=1, provider="mock", model="m", round_possible=10
    )
    collector.record_generate(
        "r1",
        snippet_id="s1",
        index=0,
        seed_id="opt-dict-force",
        generate_ms=50,
        generate_attempts=1,
        freshness_rejects=0,
        degraded=False,
        provider="mock",
        model="m",
    )
    collector.record_submit(
        "r1",
        "s1",
        submit_ms=5,
        judge_called=False,
        points_awarded=10,
        correct=True,
        partial=False,
        round_score=10,
    )
    collector.flush_round(logs, "r1", round_score=10)

    summary = analyze(reports, logs, persist=True)
    assert summary["report_count"] == 2
    assert summary["round_log_count"] == 1
    assert summary["reasons"]["ambiguous"] == 1
    assert summary["reasons"]["duplicate"] == 1
    assert summary["metrics"]["avg_generate_ms"] == 50.0
    assert summary["metrics"]["avg_submit_ms"] == 5.0
    assert summary["metrics"]["degraded_rate"] == 0.0
    assert summary["metrics"]["judge_call_rate"] == 0.0
    assert summary["top_categories"]
    assert summary["top_seeds"]
    assert isinstance(summary["alerts"], list)
    assert (logs / ANALYZE_LATEST_NAME).is_file()


def test_ops_api_and_cli_after_mock_round(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)

    with TestClient(app) as client:
        round_id = client.post("/api/round/start").json()["round_id"]
        for i in range(10):
            bug = client.post(
                "/api/round/next-bug", json={"round_id": round_id}
            ).json()
            submit = client.post(
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
            if i == 0:
                report = client.post(
                    "/api/round/report-snippet",
                    json={
                        "round_id": round_id,
                        "snippet_id": bug["snippet_id"],
                        "reason": "unfair_score",
                        "note": "slice09",
                    },
                )
                assert report.status_code == 200
            if i == 9:
                assert submit["round_complete"] is True

        analyzed = client.post("/api/ops/analyze").json()
        assert analyzed["report_count"] >= 1
        assert analyzed["round_log_count"] >= 1
        assert analyzed["reasons"]["unfair_score"] >= 1
        assert "avg_generate_ms" in analyzed["metrics"]
        assert analyzed["top_categories"] or analyzed["top_seeds"] is not None

        summary = client.get("/api/ops/summary").json()
        assert summary["report_count"] == analyzed["report_count"]

        reports = client.get("/api/ops/reports?limit=10").json()
        assert isinstance(reports, list)
        assert len(reports) >= 1
        report_id = reports[0]["report_id"]

        detail = client.get(f"/api/ops/reports/{report_id}").json()
        assert detail["report_id"] == report_id
        assert detail["reason"] == "unfair_score"
        assert detail["code"]
        assert detail["bug_summary"]
        assert detail["player_answer"]

        filtered = client.get("/api/ops/reports?reason=unfair_score").json()
        assert all(item["reason"] == "unfair_score" for item in filtered)

        ops_page = client.get("/ops")
        assert ops_page.status_code == 200
        assert b"Bugmiester Ops" in ops_page.content
        assert b"Run analyze" in ops_page.content

    # CLI analyze against the same Application Support dirs.
    monkeypatch.setattr(
        "bugmiester.__main__.default_examples_dir",
        lambda: tmp_path / "examples",
    )
    monkeypatch.setattr(
        "bugmiester.__main__.load_settings",
        lambda **_kwargs: settings,
    )
    from bugmiester.__main__ import main

    assert main(["analyze"]) == 0
    captured = capsys.readouterr()
    cli_summary = json.loads(captured.out)
    assert cli_summary["report_count"] >= 1
    assert cli_summary["round_log_count"] >= 1
    assert cli_summary["reasons"]["unfair_score"] >= 1


def test_ops_report_404(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        missing = client.get("/api/ops/reports/does-not-exist")
        assert missing.status_code == 404
