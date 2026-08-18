"""Offline golden eval for keyword (+ optional mock judge) scoring."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from bugmiester.config import ScoringSettings
from bugmiester.llm.mock_provider import MockProvider
from bugmiester.scoring import score_answer, score_keyword

GOLDEN_CASES_NAME = "golden_cases.json"


@dataclass(frozen=True)
class GoldenCase:
    id: str
    code: str
    expected_summary: str
    bug_category: str = ""
    keywords: tuple[str, ...] = ()
    good_answers: tuple[str, ...] = ()
    bad_answers: tuple[str, ...] = ()


@dataclass
class CaseFailure:
    case_id: str
    kind: str
    answer: str
    detail: str


@dataclass
class EvalReport:
    total_cases: int = 0
    good_checked: int = 0
    bad_checked: int = 0
    failures: list[CaseFailure] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total_cases": self.total_cases,
            "good_checked": self.good_checked,
            "bad_checked": self.bad_checked,
            "failure_count": len(self.failures),
            "failures": [
                {
                    "case_id": f.case_id,
                    "kind": f.kind,
                    "answer": f.answer,
                    "detail": f.detail,
                }
                for f in self.failures
            ],
        }


def golden_cases_path() -> Path:
    return Path(__file__).resolve().with_name(GOLDEN_CASES_NAME)


def load_golden_cases(path: Path | None = None) -> list[GoldenCase]:
    target = path or golden_cases_path()
    raw = json.loads(target.read_text(encoding="utf-8"))
    cases_raw = raw.get("cases") if isinstance(raw, dict) else raw
    if not isinstance(cases_raw, list):
        raise ValueError(f"Invalid golden cases file: {target}")

    cases: list[GoldenCase] = []
    for item in cases_raw:
        if not isinstance(item, dict):
            continue
        cases.append(
            GoldenCase(
                id=str(item.get("id") or f"case-{len(cases)+1}"),
                code=str(item.get("code") or ""),
                expected_summary=str(item.get("expected_summary") or ""),
                bug_category=str(item.get("bug_category") or ""),
                keywords=tuple(
                    str(k) for k in (item.get("keywords") or []) if str(k).strip()
                ),
                good_answers=tuple(
                    str(a) for a in (item.get("good_answers") or []) if str(a).strip()
                ),
                bad_answers=tuple(
                    str(a) for a in (item.get("bad_answers") or []) if str(a).strip()
                ),
            )
        )
    return cases


def _hybrid_settings() -> ScoringSettings:
    return ScoringSettings(
        mode="hybrid",
        points_per_bug=10,
        partial_credit=True,
        generosity="prefer_partial_on_low_confidence",
    )


def run_golden_eval(
    path: Path | None = None,
    *,
    include_mock_judge: bool = True,
) -> EvalReport:
    """
    Check golden good/bad answers against keyword scoring.

    When ``include_mock_judge`` is true, also run a cheap hybrid pass with the
    mock judge (no network) so paraphrase goods still get credit when keywords miss.
    """
    cases = load_golden_cases(path)
    report = EvalReport(total_cases=len(cases))
    mock = MockProvider() if include_mock_judge else None
    hybrid = _hybrid_settings()

    for case in cases:
        for answer in case.good_answers:
            report.good_checked += 1
            kw = score_keyword(
                case.expected_summary,
                answer,
                case.keywords,
                bug_category=case.bug_category or None,
                points_possible=10,
                partial_credit=True,
            )
            awarded = kw.points_awarded
            detail_bits = [f"keyword points={awarded} correct={kw.correct}"]

            if awarded <= 0 and include_mock_judge and mock is not None:
                scored = score_answer(
                    code=case.code,
                    expected_summary=case.expected_summary,
                    answer=answer,
                    keywords=case.keywords,
                    bug_category=case.bug_category or None,
                    scoring=hybrid,
                    max_judge_calls=1,
                    judge_fn=mock.judge_answer,
                )
                awarded = scored.points_awarded
                detail_bits.append(
                    f"hybrid points={scored.points_awarded} judge={scored.judge_called}"
                )

            if awarded <= 0:
                report.failures.append(
                    CaseFailure(
                        case_id=case.id,
                        kind="good",
                        answer=answer,
                        detail="; ".join(detail_bits) + " — expected credit",
                    )
                )

        for answer in case.bad_answers:
            report.bad_checked += 1
            kw = score_keyword(
                case.expected_summary,
                answer,
                case.keywords,
                bug_category=case.bug_category or None,
                points_possible=10,
                partial_credit=True,
            )
            # Bad answers must not get full credit on the keyword path.
            if kw.correct:
                report.failures.append(
                    CaseFailure(
                        case_id=case.id,
                        kind="bad",
                        answer=answer,
                        detail=f"keyword marked correct (points={kw.points_awarded})",
                    )
                )
                continue

            if include_mock_judge and mock is not None:
                scored = score_answer(
                    code=case.code,
                    expected_summary=case.expected_summary,
                    answer=answer,
                    keywords=case.keywords,
                    bug_category=case.bug_category or None,
                    scoring=hybrid,
                    max_judge_calls=1,
                    judge_fn=mock.judge_answer,
                )
                if scored.correct:
                    report.failures.append(
                        CaseFailure(
                            case_id=case.id,
                            kind="bad",
                            answer=answer,
                            detail=(
                                f"hybrid/mock judge marked correct "
                                f"(points={scored.points_awarded})"
                            ),
                        )
                    )

    return report


def format_report(report: EvalReport) -> str:
    lines = [
        f"Golden eval: {'PASS' if report.ok else 'FAIL'}",
        f"  cases: {report.total_cases}",
        f"  good answers checked: {report.good_checked}",
        f"  bad answers checked: {report.bad_checked}",
        f"  failures: {len(report.failures)}",
    ]
    for failure in report.failures:
        lines.append(
            f"  - [{failure.kind}] {failure.case_id}: "
            f"{failure.answer!r} — {failure.detail}"
        )
    return "\n".join(lines)
