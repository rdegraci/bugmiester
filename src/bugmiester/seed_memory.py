"""Persist recently used scenario seed ids across completed rounds."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

RECENT_SEEDS_FILENAME = "recent_seeds.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class RecentRoundSeeds:
    round_id: str
    seed_ids: tuple[str, ...]
    completed_at: str


def recent_seeds_path(app_dir: Path) -> Path:
    return app_dir / RECENT_SEEDS_FILENAME


def load_recent_rounds(app_dir: Path) -> list[RecentRoundSeeds]:
    path = recent_seeds_path(app_dir)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = raw.get("rounds") if isinstance(raw, dict) else None
    if not isinstance(rows, list):
        return []
    out: list[RecentRoundSeeds] = []
    for item in rows:
        parsed = _parse_round(item)
        if parsed is not None:
            out.append(parsed)
    return out


def flatten_recent_seed_ids(rounds: Sequence[RecentRoundSeeds]) -> list[str]:
    """Oldest round first. Later duplicates win recency in ``order_seed_pool``."""
    ids: list[str] = []
    for row in rounds:
        ids.extend(row.seed_ids)
    return ids


def record_completed_round_seeds(
    app_dir: Path,
    *,
    round_id: str,
    seed_ids: Sequence[str],
    keep_rounds: int,
) -> None:
    keep = max(0, int(keep_rounds))
    if keep < 1:
        return
    ids = tuple(sid for sid in seed_ids if sid)
    if not ids:
        return
    rounds = [row for row in load_recent_rounds(app_dir) if row.round_id != round_id]
    rounds.append(
        RecentRoundSeeds(
            round_id=round_id,
            seed_ids=ids,
            completed_at=_utc_now_iso(),
        )
    )
    rounds = rounds[-keep:]
    app_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "rounds": [
            {
                "round_id": row.round_id,
                "seed_ids": list(row.seed_ids),
                "completed_at": row.completed_at,
            }
            for row in rounds
        ]
    }
    path = recent_seeds_path(app_dir)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)


def _parse_round(item: Any) -> RecentRoundSeeds | None:
    if not isinstance(item, dict):
        return None
    round_id = str(item.get("round_id") or "").strip()
    completed_at = str(item.get("completed_at") or "").strip() or _utc_now_iso()
    raw_ids = item.get("seed_ids") or []
    if not round_id or not isinstance(raw_ids, list):
        return None
    seed_ids = tuple(str(sid).strip() for sid in raw_ids if str(sid).strip())
    if not seed_ids:
        return None
    return RecentRoundSeeds(
        round_id=round_id,
        seed_ids=seed_ids,
        completed_at=completed_at,
    )
