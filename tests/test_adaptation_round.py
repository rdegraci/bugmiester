"""Within-round adaptation via RoundStore (mock provider)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from bugmiester.adaptation import ADAPTIVE_ACTION_REINFORCE
from bugmiester.app import create_app
from bugmiester.config import ensure_app_dir, load_settings
from bugmiester.freshness import SEED_POOL
from bugmiester.mix import is_gnarly_seed


def _adapt_settings(tmp_path: Path, monkeypatch):
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / ".env.example").write_text(
        "OPENAI_API_KEY=replace-me\nANTHROPIC_API_KEY=replace-me\nXAI_API_KEY=replace-me\n",
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
    raw["adaptation"] = {
        "enabled": True,
        "cluster": "isolation",
        "miss_threshold": 2,
        "max_delayed_gnarly": 1,
        "cross_round": False,
    }
    (app_dir / "config.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )
    monkeypatch.setattr("bugmiester.app.default_examples_dir", lambda: examples)
    return load_settings(
        app_dir=app_dir, examples_dir=examples, load_env_into_process=False
    )


def _isolation_seed_ids() -> set[str]:
    return {
        seed.seed_id
        for seed in SEED_POOL
        if seed.category in {"concurrency", "MainActor", "sendable"}
        and not is_gnarly_seed(seed)
    }


def test_adapted_round_delays_gnarly_after_isolation_misses(
    tmp_path: Path, monkeypatch
) -> None:
    settings = _adapt_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    isolation_ids = _isolation_seed_ids()

    # Force adaptation scheduling without depending on random Common draws.
    monkeypatch.setattr(
        "bugmiester.rounds.count_cluster_misses",
        lambda bugs, cluster, bugs_per_round: 2,
    )

    with TestClient(app) as client:
        round_id = client.post("/api/round/start").json()["round_id"]
        bugs: list[dict] = []
        for _ in range(10):
            bug = client.post(
                "/api/round/next-bug", json={"round_id": round_id}
            ).json()
            bugs.append(bug)
            result = client.post(
                "/api/round/submit",
                json={
                    "round_id": round_id,
                    "snippet_id": bug["snippet_id"],
                    "answer": "idk",
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

        assert result["round_complete"] is True

        # Indices 8–9: with 2+ Common isolation misses, slot 8 stays Common.
        assert bugs[8]["difficulty_label"] == "Common"
        assert bugs[9]["difficulty_label"] == "Gnarly"

        log_path = settings.logs_dir / f"round_{round_id}.json"
        payload = json.loads(log_path.read_text(encoding="utf-8"))
        by_index = {bug["index"]: bug for bug in payload["bugs"]}
        assert by_index[8]["adaptive_action"] == ADAPTIVE_ACTION_REINFORCE
        reinforce_seed = by_index[8]["seed_id"]
        assert reinforce_seed in isolation_ids
