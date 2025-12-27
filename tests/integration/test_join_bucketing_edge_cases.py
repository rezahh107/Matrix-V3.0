from __future__ import annotations

import pandas as pd

from app.core.allocate_students import (
    _build_join_bucket_index,
    allocate_batch,
    allocate_student,
)
from app.core.policy_loader import load_policy


def _build_minimal_pool() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "mentor_name": "منتور الف",
                "alias": 101,
                "remaining_capacity": 1,
                "allocations_new": 0,
                "occupancy_ratio": 0.0,
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
                "کد کارمندی پشتیبان": 101,
                "mentor_id": "M1",
            }
        ]
    )


def test_join_bucketing_skips_unconstrained_school() -> None:
    students = pd.DataFrame(
        [
            {
                "student_id": "STD-1",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
            }
        ]
    )

    pool = _build_minimal_pool()
    pool["has_school_constraint"] = False

    policy = load_policy()

    baseline = allocate_batch(students, pool, policy=policy, use_join_buckets=False)
    optimized = allocate_batch(students, pool, policy=policy, use_join_buckets=True)

    pd.testing.assert_frame_equal(
        baseline.allocations_df.reset_index(drop=True),
        optimized.allocations_df.reset_index(drop=True),
    )


def test_join_bucketing_missing_join_key_returns_data_missing() -> None:
    policy = load_policy()
    pool = _build_minimal_pool()
    join_bucket_index = _build_join_bucket_index(pool, policy)

    student = {
        "student_id": "STD-MISS",
        "کدرشته": 1,
        "گروه آزمایشی": "تجربی",
        "دانش آموز فارغ": 0,
        "مرکز گلستان صدرا": 0,
        "مالی حکمت بنیاد": 0,
        "کد مدرسه": 1010,
    }

    result = allocate_student(
        student,
        pool,
        policy=policy,
        join_bucket_index=join_bucket_index,
    )

    assert result.mentor_row is None
    assert result.log["error_type"] == "DATA_MISSING"
