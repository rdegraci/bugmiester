"""Slice 07: hybrid / keyword / mock-judge scoring."""

from __future__ import annotations

from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from bugmiester.app import create_app
from bugmiester.config import ScoringSettings, ensure_app_dir, load_settings
from bugmiester.llm.mock_provider import MockProvider
from bugmiester.scoring import (
    JudgeResult,
    score_answer,
    score_keyword,
)


SUMMARY = "Force unwrap of a dictionary value that may be nil"
KEYWORDS = ("force unwrap", "optional", "nil", "dictionary")
CODE = 'return dict["name"]!'


def test_keyword_hit_full_credit() -> None:
    result = score_keyword(
        SUMMARY,
        "force unwrap on a nil optional from the dictionary",
        KEYWORDS,
        points_possible=10,
    )
    assert result.correct is True
    assert result.partial is False
    assert result.points_awarded == 10
    assert result.expected_summary == SUMMARY
    assert "Yes" in result.feedback


def test_keyword_miss_zero() -> None:
    result = score_keyword(
        SUMMARY,
        "memory leak in the retain cycle",
        KEYWORDS,
        points_possible=10,
    )
    assert result.correct is False
    assert result.partial is False
    assert result.points_awarded == 0
    assert result.expected_summary == SUMMARY


def test_keyword_partial_half_points() -> None:
    result = score_keyword(
        SUMMARY,
        "optional",
        KEYWORDS,
        points_possible=10,
        partial_credit=True,
    )
    assert result.correct is False
    assert result.partial is True
    assert result.points_awarded == 5
    assert result.expected_summary == SUMMARY


def test_hybrid_accepts_strong_keyword_without_judge() -> None:
    calls = {"n": 0}

    def judge(_code: str, _expected: str, _answer: str) -> JudgeResult:
        calls["n"] += 1
        return JudgeResult(True, False, "should not run", confidence=1.0)

    result = score_answer(
        code=CODE,
        expected_summary=SUMMARY,
        answer="force unwrap nil optional",
        keywords=KEYWORDS,
        scoring=ScoringSettings(mode="hybrid", points_per_bug=10),
        max_judge_calls=1,
        judge_fn=judge,
    )
    assert result.correct is True
    assert result.points_awarded == 10
    assert result.judge_called is False
    assert calls["n"] == 0


def test_hybrid_calls_judge_once_on_keyword_miss() -> None:
    calls = {"n": 0}

    def judge(_code: str, _expected: str, _answer: str) -> JudgeResult:
        calls["n"] += 1
        return JudgeResult(
            correct=True,
            partial=False,
            feedback="Judge says yes.",
            confidence=0.9,
        )

    result = score_answer(
        code=CODE,
        expected_summary=SUMMARY,
        answer="crashes when the key is absent",
        keywords=KEYWORDS,
        scoring=ScoringSettings(mode="hybrid", points_per_bug=10),
        max_judge_calls=1,
        judge_fn=judge,
    )
    assert calls["n"] == 1
    assert result.judge_called is True
    assert result.correct is True
    assert result.points_awarded == 10


def test_judge_cap_zero_skips_judge() -> None:
    calls = {"n": 0}

    def judge(_code: str, _expected: str, _answer: str) -> JudgeResult:
        calls["n"] += 1
        return JudgeResult(True, False, "yes", confidence=1.0)

    result = score_answer(
        code=CODE,
        expected_summary=SUMMARY,
        answer="totally unrelated answer text here",
        keywords=KEYWORDS,
        scoring=ScoringSettings(mode="hybrid", points_per_bug=10),
        max_judge_calls=0,
        judge_fn=judge,
    )
    assert calls["n"] == 0
    assert result.judge_called is False
    assert result.points_awarded == 0


def test_generosity_prefers_partial_on_low_confidence() -> None:
    def judge(_code: str, _expected: str, _answer: str) -> JudgeResult:
        return JudgeResult(
            correct=False,
            partial=False,
            feedback="Unsure.",
            confidence=0.2,
        )

    result = score_answer(
        code=CODE,
        expected_summary=SUMMARY,
        answer="something vague",
        keywords=KEYWORDS,
        scoring=ScoringSettings(
            mode="llm_judge",
            points_per_bug=10,
            partial_credit=True,
            generosity="prefer_partial_on_low_confidence",
        ),
        max_judge_calls=1,
        judge_fn=judge,
    )
    assert result.correct is False
    assert result.partial is True
    assert result.points_awarded == 5
    assert result.expected_summary == SUMMARY


def test_mock_provider_judge_strong() -> None:
    mock = MockProvider()
    judged = mock.judge_answer(
        CODE, SUMMARY, "force unwrap of nil optional dictionary"
    )
    assert judged.correct is True
    assert judged.confidence >= 0.5


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


def test_mock_round_sensible_scores_and_expected_summary(
    tmp_path: Path, monkeypatch
) -> None:
    settings = _mock_settings(tmp_path, monkeypatch)
    assert settings.scoring.mode == "hybrid"
    assert settings.scoring.points_per_bug == 10
    assert settings.resilience.max_judge_calls_per_submit == 1

    app = create_app(settings=settings)
    with TestClient(app) as client:
        started = client.post("/api/round/start").json()
        assert started["round_possible"] == 100
        round_id = started["round_id"]

        # First bug: strong answer → full credit.
        bug = client.post(
            "/api/round/next-bug", json={"round_id": round_id}
        ).json()
        strong = client.post(
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
        assert strong["expected_summary"]
        assert strong["feedback"]
        assert "partial" in strong
        assert strong["points_possible"] == 10
        assert strong["points_awarded"] in (5, 10)
        assert strong["round_possible"] == 100
        assert strong["round_complete"] is False
        assert strong["summary"] is None
        assert strong["round_score"] == strong["points_awarded"]

        # Second bug: clear miss → zero (or generosity partial only if judge softens).
        bug2 = client.post(
            "/api/round/next-bug", json={"round_id": round_id}
        ).json()
        miss = client.post(
            "/api/round/submit",
            json={
                "round_id": round_id,
                "snippet_id": bug2["snippet_id"],
                "answer": "completely unrelated retain cycle memory leak",
            },
        ).json()
        assert miss["expected_summary"]
        assert miss["feedback"]
        assert miss["points_awarded"] == 0
        assert miss["correct"] is False
        assert miss["partial"] is False
        assert miss["round_score"] == strong["points_awarded"]
        assert miss["round_possible"] == 100
