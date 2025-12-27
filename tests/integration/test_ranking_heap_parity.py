from dataclasses import replace

import pandas as pd

from app.core.allocate_students import allocate_batch
from app.core.policy_loader import load_policy


def _students() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "student_id": "S-1",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 10,
                "مالی حکمت بنیاد": 5,
                "کد مدرسه": 1010,
            },
            {
                "student_id": "S-2",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 10,
                "مالی حکمت بنیاد": 5,
                "کد مدرسه": 1010,
            },
            {
                "student_id": "S-3",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 10,
                "مالی حکمت بنیاد": 5,
                "کد مدرسه": 1010,
            },
        ]
    )


def _mentors() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "mentor_name": "منتور الف",
                "mentor_id": "M-1",
                "remaining_capacity": 2,
                "allocations_new": 0,
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 10,
                "مالی حکمت بنیاد": 5,
                "کد مدرسه": 1010,
                "کد کارمندی پشتیبان": "M-1",
            },
            {
                "mentor_name": "منتور ب",
                "mentor_id": "M-2",
                "remaining_capacity": 1,
                "allocations_new": 0,
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 10,
                "مالی حکمت بنیاد": 5,
                "کد مدرسه": 1010,
                "کد کارمندی پشتیبان": "M-2",
            },
        ]
    )


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    for column in normalized.columns:
        normalized[column] = normalized[column].fillna("").astype(str)
    return normalized.reset_index(drop=True)


def test_heap_queue_parity_with_legacy() -> None:
    students = _students()
    mentors = _mentors()

    legacy_policy = load_policy()
    heap_policy = replace(legacy_policy, ranking_mode="heap_queue")

    legacy_result = allocate_batch(
        students,
        mentors,
        policy=legacy_policy,
        frames_already_canonical=False,
        use_join_buckets=True,
    )
    heap_result = allocate_batch(
        students,
        mentors,
        policy=heap_policy,
        frames_already_canonical=False,
        use_join_buckets=True,
    )

    pd.testing.assert_frame_equal(
        _normalize(legacy_result.allocations_df),
        _normalize(heap_result.allocations_df),
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        _normalize(legacy_result.logs_df),
        _normalize(heap_result.logs_df),
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        _normalize(legacy_result.trace_df),
        _normalize(heap_result.trace_df),
        check_dtype=False,
    )
