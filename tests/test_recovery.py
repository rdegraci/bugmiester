"""Partial-credit recovery quiz."""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from bugmiester.app import create_app
from bugmiester.config import ensure_app_dir, load_settings
from bugmiester.llm.parse import ParseError, parse_recovery_payload
from bugmiester.recovery import (
    assemble_options,
    fill_from_seed_bank,
    filter_distractors,
    too_close_to_expected,
)
from bugmiester.scoring import score_keyword


def _partial_answer(stored) -> str:
    candidates = list(stored.keywords) + stored.bug_summary.split() + [stored.bug_category]
    for cand in candidates:
        word = str(cand).strip().split()[0]
        if len(word) < 3:
            continue
        scored = score_keyword(
            stored.bug_summary,
            word,
            stored.keywords,
            bug_category=stored.bug_category,
            points_possible=10,
        )
        if scored.partial and not scored.correct:
            return word
    return "optional"


def _start_pending(client, app):
    round_id = client.post("/api/round/start").json()["round_id"]
    bug = client.post("/api/round/next-bug", json={"round_id": round_id}).json()
    stored = app.state.rounds.get(round_id).snippets[bug["snippet_id"]]
    return round_id, bug, _partial_answer(stored)


def _mock_settings(tmp_path: Path, monkeypatch, **recovery_overrides):
    examples = tmp_path / "examples"
    examples.mkdir()
    (examples / ".env.example").write_text(
        "OPENAI_API_KEY=replace-me\nANTHROPIC_API_KEY=replace-me\nXAI_API_KEY=replace-me\n",
        encoding="utf-8",
    )
    repo_example = Path(__file__).resolve().parents[1] / "config.yaml.example"
    (examples / "config.yaml.example").write_text(
        repo_example.read_text(encoding="utf-8"), encoding="utf-8"
    )
    app_dir = tmp_path / "app"
    ensure_app_dir(app_dir=app_dir, examples_dir=examples)
    raw = yaml.safe_load((app_dir / "config.yaml").read_text(encoding="utf-8"))
    raw["llm"]["provider"] = "mock"
    if recovery_overrides:
        raw.setdefault("recovery", {})
        raw["recovery"].update(recovery_overrides)
    (app_dir / "config.yaml").write_text(
        yaml.safe_dump(raw, sort_keys=False), encoding="utf-8"
    )
    monkeypatch.setattr("bugmiester.app.default_examples_dir", lambda: examples)
    return load_settings(
        app_dir=app_dir, examples_dir=examples, load_env_into_process=False
    )


def test_parse_recovery_payload() -> None:
    parsed = parse_recovery_payload(
        {"distractors": ["Wrong A", "Wrong B", "Wrong C"]},
        needed=3,
    )
    assert parsed == ["Wrong A", "Wrong B", "Wrong C"]


def test_parse_recovery_rejects_short_list() -> None:
    try:
        parse_recovery_payload({"distractors": ["only one"]}, needed=3)
        assert False, "expected ParseError"
    except ParseError:
        pass


def test_too_close_rejects_paraphrase() -> None:
    expected = "Force unwrap of a dictionary value that may be nil"
    assert too_close_to_expected(expected, expected) is True
    assert too_close_to_expected(
        "Force unwrap of a dictionary value that may be nil.",
        expected,
    ) is True
    assert too_close_to_expected(
        "Force unwrap of a dictionary value that is nil",
        expected,
    ) is True
    assert too_close_to_expected(
        "Missing await on an async call",
        expected,
    ) is False


def test_too_close_keeps_nearby_wrong_claim() -> None:
    expected = "TextField needs a Binding; missing $ on name"
    assert too_close_to_expected(
        "Text displays with a blank username",
        expected,
    ) is False
    assert too_close_to_expected(
        "Use @Binding instead of @State for username",
        expected,
    ) is False


def test_filter_distractors_prefers_player_partial() -> None:
    expected = "TextField needs a Binding; missing $ on name"
    player = "Text displays with blank username"
    filtered = filter_distractors(
        ["Integer overflow when the counter wraps", "Missing await on fetch"],
        expected,
        needed=3,
        player_answer=player,
    )
    assert filtered[0] == player
    assert len(filtered) == 3
    assert expected not in filtered


def test_fill_from_seed_bank_prefers_same_category() -> None:
    expected = "TextField needs a Binding; missing $ on name"
    filled = fill_from_seed_bank(
        expected,
        [],
        needed=3,
        bug_category="SwiftUI state",
        player_answer="Text displays with blank username",
    )
    assert filled[0] == "Text displays with blank username"
    assert len(filled) == 3
    from bugmiester.llm.mock_provider import SEED_SNIPPETS

    swiftui = {
        snip.bug_summary
        for snip in SEED_SNIPPETS.values()
        if snip.bug_category == "SwiftUI state"
        and snip.bug_summary != expected
    }
    assert any(item in swiftui for item in filled[1:])


def test_assemble_options_shuffles_without_correct_flag() -> None:
    options = assemble_options(
        "Real bug",
        ["Wrong A", "Wrong B", "Wrong C"],
        choice_count=4,
    )
    assert options is not None
    assert len(options) == 4
    assert sum(1 for opt in options if opt.correct) == 1


def test_partial_opens_quiz_hides_expected(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        round_id, bug, answer = _start_pending(client, app)
        result = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "answer": answer,
            },
        ).json()
        assert result["partial"] is True
        assert result["correct"] is False
        assert result["recovery_available"] is True
        assert result["expected_summary"] == ""
        assert "Expected:" not in (result["feedback"] or "")
        assert len(result["recovery_options"]) == 4
        texts = [opt["text"] for opt in result["recovery_options"]]
        assert len(set(texts)) == 4
        for opt in result["recovery_options"]:
            assert set(opt.keys()) == {"id", "text"}
        assert result["round_complete"] is False

        # Prefetch still works while the quiz is open.
        nxt = client.post(
            "/api/round/next-bug", json={"round_id": round_id}
        ).json()
        assert nxt["index"] == 1
        assert "bug_summary" not in nxt


def test_correct_pick_upgrades_to_full(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        round_id, bug, answer = _start_pending(client, app)
        submitted = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "answer": answer,
            },
        ).json()
        assert submitted["recovery_available"] is True
        partial_points = submitted["points_awarded"]
        store = app.state.rounds
        stored = store.get(round_id).snippets[bug["snippet_id"]]
        correct_id = next(
            opt.option_id for opt in stored.recovery_options if opt.correct
        )
        recovered = client.post(
            "/api/round/recover",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "option_id": correct_id,
            },
        ).json()
        assert recovered["upgraded"] is True
        assert recovered["correct"] is True
        assert recovered["partial"] is False
        assert recovered["points_awarded"] == submitted["points_possible"]
        assert recovered["points_awarded"] > partial_points
        assert recovered["expected_summary"]
        assert recovered["recovery_available"] is False


def test_continue_keeps_partial(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        round_id, bug, answer = _start_pending(client, app)
        submitted = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "answer": answer,
            },
        ).json()
        recovered = client.post(
            "/api/round/recover",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "option_id": None,
            },
        ).json()
        assert recovered["upgraded"] is False
        assert recovered["partial"] is True
        assert recovered["points_awarded"] == submitted["points_awarded"]
        assert recovered["expected_summary"]
        assert "Kept partial" in recovered["feedback"]


def test_wrong_pick_keeps_partial(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        round_id, bug, answer = _start_pending(client, app)
        submitted = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "answer": answer,
            },
        ).json()
        store = app.state.rounds
        stored = store.get(round_id).snippets[bug["snippet_id"]]
        wrong_id = next(
            opt.option_id for opt in stored.recovery_options if not opt.correct
        )
        recovered = client.post(
            "/api/round/recover",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "option_id": wrong_id,
            },
        ).json()
        assert recovered["upgraded"] is False
        assert recovered["partial"] is True
        assert recovered["points_awarded"] == submitted["points_awarded"]
        assert recovered["expected_summary"]


def test_seed_bank_when_llm_calls_disabled(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch, max_llm_calls=0)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        round_id, bug, answer = _start_pending(client, app)
        result = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "answer": answer,
            },
        ).json()
        assert result["recovery_available"] is True
        assert len(result["recovery_options"]) == 4


def test_recovery_disabled_reveals_expected(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch, enabled=False)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        round_id, bug, answer = _start_pending(client, app)
        result = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": bug["snippet_id"],
                "answer": answer,
            },
        ).json()
        assert result["partial"] is True
        assert result["recovery_available"] is False
        assert result["expected_summary"]



def test_ui_has_recovery_and_spinner(tmp_path: Path, monkeypatch) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    app = create_app(settings=settings)
    with TestClient(app) as client:
        index = client.get("/")
        js = client.get("/app.js")
    assert b"recovery-panel" in index.content
    assert b"progress-spinner" in index.content
    assert "Checking your answer" in js.text
    assert "Keep partial credit" in index.text
    assert "/api/round/recover" in js.text
