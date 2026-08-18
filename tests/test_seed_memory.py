"""Across-round seed memory."""

from __future__ import annotations

from pathlib import Path

from bugmiester.freshness import SEED_POOL
from bugmiester.seed_memory import (
    flatten_recent_seed_ids,
    load_recent_rounds,
    recent_seeds_path,
    record_completed_round_seeds,
)


def test_record_completed_round_seeds_trims_window(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    first = [seed.seed_id for seed in SEED_POOL[:10]]
    second = [seed.seed_id for seed in SEED_POOL[10:20]]
    third = [seed.seed_id for seed in SEED_POOL[20:30]]
    record_completed_round_seeds(
        app_dir, round_id="r1", seed_ids=first, keep_rounds=2
    )
    record_completed_round_seeds(
        app_dir, round_id="r2", seed_ids=second, keep_rounds=2
    )
    record_completed_round_seeds(
        app_dir, round_id="r3", seed_ids=third, keep_rounds=2
    )
    rounds = load_recent_rounds(app_dir)
    assert [row.round_id for row in rounds] == ["r2", "r3"]
    assert flatten_recent_seed_ids(rounds) == second + third
    assert recent_seeds_path(app_dir).is_file()


def test_record_completed_round_seeds_disabled(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    record_completed_round_seeds(
        app_dir,
        round_id="r1",
        seed_ids=[SEED_POOL[0].seed_id],
        keep_rounds=0,
    )
    assert load_recent_rounds(app_dir) == []
    assert not recent_seeds_path(app_dir).exists()


def test_load_recent_rounds_corrupt_file_is_empty(tmp_path: Path) -> None:
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    recent_seeds_path(app_dir).write_text("{not json", encoding="utf-8")
    assert load_recent_rounds(app_dir) == []
