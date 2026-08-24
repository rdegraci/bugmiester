"""Persist cluster weakness across completed rounds (Application Support)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from bugmiester.adaptation import (
    AnsweredBug,
    normalize_adaptive_cluster,
    tally_cluster_common_outcomes,
)

WEAKNESS_FILENAME = "weakness.json"
WEAKNESS_MISS_CAP = 10
CLEAN_ROUND_MISS_DECAY = 1
CROSS_ROUND_THRESHOLD_BONUS = 1  # stored misses needed to lower threshold by 1


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class ClusterWeakness:
    misses: int = 0
    hits: int = 0
    updated_at: str = ""


def weakness_path(app_dir: Path) -> Path:
    return app_dir / WEAKNESS_FILENAME


def load_weakness(app_dir: Path) -> dict[str, ClusterWeakness]:
    path = weakness_path(app_dir)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    clusters = raw.get("clusters") if isinstance(raw, dict) else None
    if not isinstance(clusters, dict):
        return {}
    out: dict[str, ClusterWeakness] = {}
    for key, value in clusters.items():
        parsed = _parse_cluster(key, value)
        if parsed is not None:
            out[parsed[0]] = parsed[1]
    return out


def get_cluster_misses(app_dir: Path, cluster: str) -> int:
    row = load_weakness(app_dir).get(normalize_adaptive_cluster(cluster))
    if row is None:
        return 0
    return max(0, int(row.misses))


def effective_miss_threshold(
    base_threshold: int,
    stored_misses: int,
    *,
    cross_round: bool,
) -> int:
    """Lower the within-round threshold when cross-round weakness is elevated."""
    base = max(1, int(base_threshold))
    if not cross_round:
        return base
    bonus = max(0, int(stored_misses))
    lowered = base - (bonus // CROSS_ROUND_THRESHOLD_BONUS)
    return max(1, lowered)


def should_bias_first_common_slot(
    stored_misses: int,
    *,
    cross_round: bool,
    base_threshold: int,
) -> bool:
    """Nudge the first Common bug toward the weak cluster after rough sessions."""
    if not cross_round:
        return False
    if max(1, int(base_threshold)) <= 1:
        return False
    return int(stored_misses) >= CROSS_ROUND_THRESHOLD_BONUS


def record_completed_round_weakness(
    app_dir: Path,
    *,
    round_id: str,
    cluster: str,
    bugs: Sequence[AnsweredBug],
    bugs_per_round: int,
) -> ClusterWeakness | None:
    """
    Update weakness counters from a completed round, apply clean-round decay, persist.

    Returns the updated cluster row, or None when there is nothing to record.
    """
    cluster_id = normalize_adaptive_cluster(cluster)
    hits, misses = tally_cluster_common_outcomes(
        bugs, cluster_id, bugs_per_round
    )
    if hits == 0 and misses == 0:
        # Still apply clean-round decay when the player had no cluster bugs in Common.
        hits = 0
        misses = 0

    state = load_weakness(app_dir)
    current = state.get(cluster_id, ClusterWeakness())
    new_misses = current.misses + misses
    new_hits = current.hits + hits

    if misses == 0 and current.misses > 0:
        new_misses = max(0, new_misses - CLEAN_ROUND_MISS_DECAY)

    new_misses = min(WEAKNESS_MISS_CAP, max(0, new_misses))
    updated = ClusterWeakness(
        misses=new_misses,
        hits=new_hits,
        updated_at=_utc_now_iso(),
    )
    state[cluster_id] = updated
    _write_weakness(app_dir, state, round_id=round_id)
    return updated


def weakness_snapshot(app_dir: Path) -> dict[str, Any]:
    """JSON-serializable weakness view for ops / analyze."""
    rows = load_weakness(app_dir)
    return {
        "clusters": {
            cluster_id: {
                "misses": row.misses,
                "hits": row.hits,
                "updated_at": row.updated_at,
            }
            for cluster_id, row in sorted(rows.items())
        }
    }


def _parse_cluster(key: object, value: Any) -> tuple[str, ClusterWeakness] | None:
    cluster_id = normalize_adaptive_cluster(key)
    if not isinstance(value, Mapping):
        return None
    try:
        misses = int(value.get("misses", 0))
    except (TypeError, ValueError):
        misses = 0
    try:
        hits = int(value.get("hits", 0))
    except (TypeError, ValueError):
        hits = 0
    updated_at = str(value.get("updated_at") or "").strip()
    return cluster_id, ClusterWeakness(
        misses=max(0, min(WEAKNESS_MISS_CAP, misses)),
        hits=max(0, hits),
        updated_at=updated_at or _utc_now_iso(),
    )


def _write_weakness(
    app_dir: Path,
    clusters: dict[str, ClusterWeakness],
    *,
    round_id: str,
) -> None:
    app_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_round_id": round_id,
        "clusters": {
            cluster_id: {
                "misses": row.misses,
                "hits": row.hits,
                "updated_at": row.updated_at or _utc_now_iso(),
            }
            for cluster_id, row in sorted(clusters.items())
        },
    }
    path = weakness_path(app_dir)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
