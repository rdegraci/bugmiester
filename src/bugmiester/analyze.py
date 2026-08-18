"""Aggregate reports/ + logs/ → summary JSON for ops and CLI."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bugmiester.reports import REPORT_REASONS, list_reports


ANALYZE_LATEST_NAME = "analyze_latest.json"

# Simple alert thresholds (tune in playtest; keep in code for MVP).
DEGRADED_RATE_ALERT = 0.2
AVG_GENERATE_ATTEMPTS_ALERT = 1.5
FRESHNESS_REJECT_RATE_ALERT = 0.3  # share of bugs with ≥1 reject (last N)
JUDGE_CALL_RATE_ALERT = 0.85
LAST_BUGS_WINDOW = 20
TOP_N = 5


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def load_round_logs(logs_dir: Path) -> list[dict[str, Any]]:
    if not logs_dir.is_dir():
        return []
    logs: list[dict[str, Any]] = []
    for path in sorted(logs_dir.glob("round_*.json")):
        payload = _read_json(path)
        if payload is not None:
            logs.append(payload)
    return logs


def _empty_reasons() -> dict[str, int]:
    return {reason: 0 for reason in sorted(REPORT_REASONS)}


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


def _bug_entries(round_logs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bugs: list[dict[str, Any]] = []
    for round_log in round_logs:
        for bug in round_log.get("bugs") or []:
            if isinstance(bug, dict):
                bugs.append(bug)
    return bugs


def _build_alerts(
    *,
    report_count: int,
    round_log_count: int,
    metrics: dict[str, float],
    recent_bugs: list[dict[str, Any]],
) -> list[str]:
    alerts: list[str] = []
    if report_count == 0 and round_log_count == 0:
        alerts.append("No reports or round logs yet")
        return alerts

    if metrics["degraded_rate"] >= DEGRADED_RATE_ALERT:
        alerts.append(
            f"High degraded rate ({metrics['degraded_rate']:.0%}) — "
            "generate fallbacks are common"
        )
    if metrics["avg_generate_attempts"] >= AVG_GENERATE_ATTEMPTS_ALERT:
        alerts.append(
            f"High avg generate attempts ({metrics['avg_generate_attempts']}) — "
            "check freshness rejects / JSON repair"
        )
    if recent_bugs:
        window = recent_bugs[-LAST_BUGS_WINDOW:]
        reject_hits = sum(
            1 for bug in window if int(bug.get("freshness_rejects") or 0) > 0
        )
        reject_rate = reject_hits / len(window)
        if reject_rate >= FRESHNESS_REJECT_RATE_ALERT:
            alerts.append(
                f"High freshness reject rate in last {len(window)} bugs "
                f"({reject_rate:.0%})"
            )
    if metrics["judge_call_rate"] >= JUDGE_CALL_RATE_ALERT:
        alerts.append(
            f"High judge call rate ({metrics['judge_call_rate']:.0%}) — "
            "keyword path may be too weak"
        )
    return alerts


def analyze(
    reports_dir: Path,
    logs_dir: Path,
    *,
    persist: bool = True,
) -> dict[str, Any]:
    """
    Aggregate Application Support reports/ + logs/ into a summary dict.

    When ``persist`` is true, writes ``logs/analyze_latest.json``.
    """
    reports = list_reports(reports_dir, limit=10_000)
    # list_reports returns metadata; reload full for category/seed when needed.
    # Metadata already includes bug_category / seed_id from list helper.
    round_logs = load_round_logs(logs_dir)
    bugs = _bug_entries(round_logs)

    reasons = _empty_reasons()
    category_counts: Counter[str] = Counter()
    seed_counts: Counter[str] = Counter()

    for report in reports:
        reason = str(report.get("reason") or "other")
        if reason not in reasons:
            reasons[reason] = 0
        reasons[reason] += 1
        category = str(report.get("bug_category") or "").strip()
        if category:
            category_counts[category] += 1
        seed_id = str(report.get("seed_id") or "").strip()
        if seed_id:
            seed_counts[seed_id] += 1

    generate_ms = [
        float(bug["generate_ms"])
        for bug in bugs
        if bug.get("generate_ms") is not None
    ]
    submit_ms = [
        float(bug["submit_ms"])
        for bug in bugs
        if bug.get("submit_ms") is not None
    ]
    attempts = [
        float(bug.get("generate_attempts") or 0) for bug in bugs
    ]
    degraded_flags = [bool(bug.get("degraded")) for bug in bugs]
    judge_flags = [bool(bug.get("judge_called")) for bug in bugs]

    bug_count = len(bugs)
    metrics = {
        "avg_generate_ms": _avg(generate_ms),
        "avg_submit_ms": _avg(submit_ms),
        "degraded_rate": (
            round(sum(1 for d in degraded_flags if d) / bug_count, 4)
            if bug_count
            else 0.0
        ),
        "avg_generate_attempts": _avg(attempts) if attempts else 0.0,
        "judge_call_rate": (
            round(sum(1 for j in judge_flags if j) / bug_count, 4)
            if bug_count
            else 0.0
        ),
    }

    top_categories = [
        {"category": name, "reports": count}
        for name, count in category_counts.most_common(TOP_N)
    ]
    top_seeds = [
        {"seed_id": name, "reports": count}
        for name, count in seed_counts.most_common(TOP_N)
    ]

    summary: dict[str, Any] = {
        "generated_at": _utc_now_iso(),
        "report_count": len(reports),
        "round_log_count": len(round_logs),
        "reasons": reasons,
        "metrics": metrics,
        "top_categories": top_categories,
        "top_seeds": top_seeds,
        "alerts": _build_alerts(
            report_count=len(reports),
            round_log_count=len(round_logs),
            metrics=metrics,
            recent_bugs=bugs,
        ),
    }

    if persist:
        logs_dir.mkdir(parents=True, exist_ok=True)
        path = logs_dir / ANALYZE_LATEST_NAME
        path.write_text(
            json.dumps(summary, indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )

    return summary


def load_cached_summary(logs_dir: Path) -> dict[str, Any] | None:
    path = logs_dir / ANALYZE_LATEST_NAME
    if not path.is_file():
        return None
    return _read_json(path)


def get_summary(
    reports_dir: Path,
    logs_dir: Path,
    *,
    analyze_on_miss: bool = True,
    persist_on_miss: bool = False,
) -> dict[str, Any]:
    """Return cached summary, or compute when missing / requested."""
    cached = load_cached_summary(logs_dir)
    if cached is not None:
        return cached
    if analyze_on_miss:
        return analyze(reports_dir, logs_dir, persist=persist_on_miss)
    return analyze(reports_dir, logs_dir, persist=False)
