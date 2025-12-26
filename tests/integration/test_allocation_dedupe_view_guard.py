from __future__ import annotations

import pandas as pd

from app.core.allocate_students import allocate_student
from app.core.policy_loader import load_policy


def _single_student() -> dict[str, object]:
    return {
        "student_id": "STD-001",
        "کدرشته": 27,
        "گروه_آزمایشی": 27,
        "جنسیت": 1,
        "دانش_آموز_فارغ": 0,
        "مرکز_گلستان_صدرا": 1,
        "مالی_حکمت_بنیاد": 0,
        "کد_مدرسه": 3581,
    }


def _single_pool() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "پشتیبان": ["زهرا"],
            "کد کارمندی پشتیبان": ["EMP-001"],
            "کدرشته": [27],
            "کدرشته | group_code": [27],
            "گروه آزمایشی": [27],
            "جنسیت": [1],
            "جنسیت | gender": [1],
            "دانش آموز فارغ": [0],
            "دانش آموز فارغ | graduation_status": [0],
            "مرکز گلستان صدرا": [1],
            "مرکز گلستان صدرا | center": [1],
            "مالی حکمت بنیاد": [0],
            "مالی حکمت بنیاد | finance": [0],
            "کد مدرسه": [3581],
            "کد مدرسه | school_code": [3581],
            "remaining_capacity": [2],
            "allocations_new": [0],
            "occupancy_ratio": [0.0],
        }
    )


def test_pool_state_view_remains_unchanged_when_view_used() -> None:
    policy = load_policy()
    pool = _single_pool()
    pool_state_view = pool.copy(deep=False)
    baseline_state = pool_state_view.copy(deep=True)

    student = _single_student()

    result = allocate_student(
        student,
        pool,
        policy=policy,
        pool_state_view=pool_state_view,
    )

    assert result.log["allocation_status"] == "success"
    pd.testing.assert_frame_equal(pool_state_view, baseline_state, check_dtype=False)
