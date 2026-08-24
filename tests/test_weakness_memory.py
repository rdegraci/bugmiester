"""Cross-round weakness.json persistence."""

from __future__ import annotations

from pathlib import Path

from bugmiester.adaptation import AnsweredBug
from bugmiester.weakness_memory import (
    CLEAN_ROUND_MISS_DECAY,
    effective_miss_threshold,
    get_cluster_misses,
    load_weakness,
    record_completed_round_weakness,
    should_bias_first_common_slot,
    weakness_path,
    weakness_snapshot,
)


def _answered(
    index: int,
    category: str,
    *,
    correct: bool,
    partial: bool = False,
) -> AnsweredBug:
    return AnsweredBug(
        index=index,
        bug_category=category,
        answered=True,
        correct=correct,
        partial=partial,
        player_answer="idk" if not correct else "await actor",
    )


def test_record_and_load_weakness(tmp_path: Path) -> None:
    bugs = [
        _answered(3, "concurrency", correct=False),
        _answered(4, "MainActor", correct=False),
    ]
    row = record_completed_round_weakness(
        tmp_path,
        round_id="r1",
        cluster="isolation",
        bugs=bugs,
        bugs_per_round=10,
    )
    assert row is not None
    assert row.misses == 2
    assert row.hits == 0
    assert weakness_path(tmp_path).is_file()
    assert get_cluster_misses(tmp_path, "isolation") == 2


def test_clean_round_decays_stored_misses(tmp_path: Path) -> None:
    record_completed_round_weakness(
        tmp_path,
        round_id="r1",
        cluster="isolation",
        bugs=[_answered(3, "concurrency", correct=False)],
        bugs_per_round=10,
    )
    record_completed_round_weakness(
        tmp_path,
        round_id="r2",
        cluster="isolation",
        bugs=[_answered(5, "captures", correct=False)],
        bugs_per_round=10,
    )
    assert get_cluster_misses(tmp_path, "isolation") == max(
        0, 1 - CLEAN_ROUND_MISS_DECAY
    )


def test_effective_miss_threshold_lowers_when_weak() -> None:
    assert effective_miss_threshold(2, 0, cross_round=False) == 2
    assert effective_miss_threshold(2, 0, cross_round=True) == 2
    assert effective_miss_threshold(2, 2, cross_round=True) == 1
    assert effective_miss_threshold(2, 4, cross_round=True) == 1


def test_should_bias_first_common_slot() -> None:
    assert should_bias_first_common_slot(0, cross_round=True, base_threshold=2) is False
    assert should_bias_first_common_slot(2, cross_round=True, base_threshold=2) is True
    assert should_bias_first_common_slot(2, cross_round=False, base_threshold=2) is False


def test_weakness_snapshot(tmp_path: Path) -> None:
    record_completed_round_weakness(
        tmp_path,
        round_id="r1",
        cluster="isolation",
        bugs=[_answered(3, "sendable", correct=True)],
        bugs_per_round=10,
    )
    snap = weakness_snapshot(tmp_path)
    assert snap["clusters"]["isolation"]["hits"] == 1
    assert snap["clusters"]["isolation"]["misses"] == 0
    assert load_weakness(tmp_path)["isolation"].hits == 1
