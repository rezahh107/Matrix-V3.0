from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.allocate_students import allocate_batch
from app.core.policy_loader import load_policy

DATASET_DIR = Path("tests/data/golden_perf/v1")
BASELINE_DECISIONS = DATASET_DIR / "decisions_baseline.csv"


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.fillna("").copy()
    for column in normalized.columns:
        normalized[column] = normalized[column].astype(str)
    return normalized.reset_index(drop=True)


def _load_perf_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    students = pd.read_csv(DATASET_DIR / "students.csv")
    mentors = pd.read_csv(DATASET_DIR / "mentors.csv")
    return students, mentors


def test_join_bucketing_matches_baseline() -> None:
    students, mentors = _load_perf_dataset()
    policy = load_policy()

    result = allocate_batch(
        students,
        mentors,
        policy=policy,
        frames_already_canonical=True,
        use_join_buckets=True,
    )
    expected = pd.read_csv(BASELINE_DECISIONS)

    actual_allocations = result.allocations_df.sort_values(
        ["student_id", "mentor_id"]
    ).reset_index(drop=True)
    expected_allocations = expected.sort_values(["student_id", "mentor_id"]).reset_index(
        drop=True
    )

    pd.testing.assert_frame_equal(
        _normalize(actual_allocations),
        _normalize(expected_allocations),
        check_dtype=False,
    )


def test_join_bucketing_parity_off_vs_on() -> None:
    students, mentors = _load_perf_dataset()
    policy = load_policy()

    baseline = allocate_batch(
        students,
        mentors,
        policy=policy,
        frames_already_canonical=True,
        use_join_buckets=False,
    )
    optimized = allocate_batch(
        students,
        mentors,
        policy=policy,
        frames_already_canonical=True,
        use_join_buckets=True,
    )

    baseline_allocations = baseline.allocations_df.sort_values(
        ["student_id", "mentor_id"]
    ).reset_index(drop=True)
    optimized_allocations = optimized.allocations_df.sort_values(
        ["student_id", "mentor_id"]
    ).reset_index(drop=True)

    pd.testing.assert_frame_equal(
        _normalize(baseline_allocations),
        _normalize(optimized_allocations),
        check_dtype=False,
    )


def test_join_bucketing_deterministic() -> None:
    students, mentors = _load_perf_dataset()
    policy = load_policy()

    first = allocate_batch(
        students,
        mentors,
        policy=policy,
        frames_already_canonical=True,
        use_join_buckets=True,
    )
    second = allocate_batch(
        students,
        mentors,
        policy=policy,
        frames_already_canonical=True,
        use_join_buckets=True,
    )

    pd.testing.assert_frame_equal(
        first.allocations_df.reset_index(drop=True),
        second.allocations_df.reset_index(drop=True),
    )
