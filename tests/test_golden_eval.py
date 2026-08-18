"""Slice 15: golden eval stubs."""

from __future__ import annotations

from bugmiester.eval import (
    format_report,
    golden_cases_path,
    load_golden_cases,
    run_golden_eval,
)
from bugmiester.__main__ import main as cli_main


def test_golden_cases_file_has_enough_cases() -> None:
    cases = load_golden_cases()
    assert golden_cases_path().is_file()
    assert 10 <= len(cases) <= 30
    for case in cases:
        assert case.id
        assert case.code.strip()
        assert case.expected_summary.strip()
        assert case.good_answers
        assert case.bad_answers


def test_golden_eval_passes_keyword_and_mock_judge() -> None:
    report = run_golden_eval(include_mock_judge=True)
    assert report.ok, format_report(report)
    assert report.good_checked >= 20
    assert report.bad_checked >= 20


def test_cli_eval_exits_zero(capsys) -> None:
    assert cli_main(["eval"]) == 0
    out = capsys.readouterr().out
    assert "PASS" in out
    assert "cases:" in out
