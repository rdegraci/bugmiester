"""Persist player “bad snippet” reports under Application Support."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_REASONS = frozenset(
    {
        "ambiguous",
        "does_not_compile",
        "duplicate",
        "unfair_score",
        "other",
    }
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_reason(reason: str) -> str:
    cleaned = (reason or "").strip().lower().replace(" ", "_").replace("-", "_")
    if cleaned not in REPORT_REASONS:
        raise ValueError(
            f"Invalid report reason '{reason}'. "
            f"Expected one of: {', '.join(sorted(REPORT_REASONS))}"
        )
    return cleaned


def write_report(
    reports_dir: Path,
    *,
    round_id: str,
    snippet_id: str,
    reason: str,
    note: str = "",
    code: str,
    bug_summary: str,
    bug_category: str = "",
    seed_id: str = "",
    player_answer: str = "",
    points_awarded: int | None = None,
    points_possible: int | None = None,
    correct: bool | None = None,
    partial: bool | None = None,
    provider: str = "",
    model: str = "",
    degraded: bool = False,
) -> tuple[str, Path]:
    """
    Write a report JSON file. Returns (report_id, path).
    """
    reason_norm = normalize_reason(reason)
    report_id = str(uuid.uuid4())
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"report_{report_id}.json"

    payload: dict[str, Any] = {
        "report_id": report_id,
        "created_at": _utc_now_iso(),
        "round_id": round_id,
        "snippet_id": snippet_id,
        "reason": reason_norm,
        "note": note or "",
        "code": code,
        "bug_summary": bug_summary,
        "bug_category": bug_category,
        "seed_id": seed_id,
        "player_answer": player_answer,
        "points_awarded": points_awarded,
        "points_possible": points_possible,
        "correct": correct,
        "partial": partial,
        "provider": provider,
        "model": model,
        "degraded": degraded,
    }
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return report_id, path
