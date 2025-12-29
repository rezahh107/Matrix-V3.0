from __future__ import annotations

import pandas as pd

from app.core.allocate_students import allocate_batch
from app.core.common.types import CANONICAL_TRACE_ORDER
from app.core.policy_loader import load_policy


def _build_inputs() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    policy = load_policy()
    capacity_column = policy.stage_column("capacity_gate")
    if capacity_column is None:
        raise RuntimeError("Policy missing capacity_gate column")
    students = pd.DataFrame(
        [
            {
                "student_id": "S-1",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
            },
            {
                "student_id": "S-2",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
            },
        ]
    )
    pool = pd.DataFrame(
        [
            {
                "پشتیبان": "Mentor A",
                "کد کارمندی پشتیبان": "EMP-1",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
                capacity_column: 1,
                "occupancy_ratio": 0.1,
                "allocations_new": 0,
                "mentor_sort_key": 1,
            },
            {
                "پشتیبان": "Mentor B",
                "کد کارمندی پشتیبان": "EMP-2",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
                capacity_column: 2,
                "occupancy_ratio": 0.2,
                "allocations_new": 0,
                "mentor_sort_key": 2,
            },
        ]
    )
    return students, pool, capacity_column


def _sort_trace(df: pd.DataFrame) -> pd.DataFrame:
    order = {stage: idx for idx, stage in enumerate(CANONICAL_TRACE_ORDER)}
    if "student_id" in df.columns and "stage" in df.columns:
        return (
            df.assign(_stage_order=df["stage"].map(order))
            .sort_values(["student_id", "_stage_order"])
            .drop(columns=["_stage_order"])
            .reset_index(drop=True)
        )
    return df.reset_index(drop=True)


def _normalize_frames(result: object) -> dict[str, pd.DataFrame]:
    pool_df = result.pool_output
    pool_sorted = (
        pool_df.sort_values("mentor_id").reset_index(drop=True)
        if "mentor_id" in pool_df.columns
        else pool_df.sort_index().reset_index(drop=True)
    )
    result_frames = {
        "allocations": result.allocations_df.sort_values("student_id").reset_index(drop=True),
        "pool": pool_sorted,
        "logs": result.logs_df.sort_values("student_id").reset_index(drop=True),
        "trace": _sort_trace(result.trace_df),
    }
    return result_frames


def test_shuffle_inputs_does_not_change_outputs() -> None:
    students, pool, _ = _build_inputs()
    baseline = allocate_batch(students, pool)
    shuffled_students = students.sample(frac=1, random_state=7).reset_index(drop=True)
    shuffled_pool = pool.sample(frac=1, random_state=11).reset_index(drop=True)

    shuffled = allocate_batch(shuffled_students, shuffled_pool)

    for key, frame in _normalize_frames(baseline).items():
        pd.testing.assert_frame_equal(frame, _normalize_frames(shuffled)[key], check_like=True)


def test_adding_irrelevant_column_does_not_change_outputs() -> None:
    students, pool, _ = _build_inputs()
    baseline = allocate_batch(students, pool)
    students_extra = students.assign(extra_note="noop")
    pool_extra = pool.assign(unused_pool_tag="noop")

    enriched = allocate_batch(students_extra, pool_extra)

    baseline_frames = _normalize_frames(baseline)
    enriched_frames = _normalize_frames(enriched)
    for key, frame in baseline_frames.items():
        other = enriched_frames[key]
        if key == "pool":
            other = other.loc[:, frame.columns]
        pd.testing.assert_frame_equal(frame, other, check_like=True)
