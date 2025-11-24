import pandas as pd

from app.core import allocate_students
from app.core.allocate_students import (
    _collect_join_key_map,
    _normalize_join_key_name,
    allocate_batch,
)
from app.core.common.columns import canonicalize_headers
from app.core.policy_loader import load_policy


def test_allocation_rejects_mismatched_join_keys(monkeypatch):
    policy = load_policy()

    students = pd.DataFrame(
        [
            {
                "student_id": "S-1",
                "کدرشته": 3,
                "گروه آزمایشی": 3,
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 0,
            }
        ]
    )

    pool = pd.DataFrame(
        [
            {
                "کد کارمندی پشتیبان": "M-1",
                "پشتیبان": "Mentor One",
                "کدرشته": 21,
                "گروه آزمایشی": 21,
                "جنسیت": 0,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 0,
                "remaining_capacity": 1,
            }
        ]
    )

    monkeypatch.setattr(
        allocate_students,
        "apply_join_filters",
        lambda pool, student, **_: pool,
    )

    allocations_df, _, logs_df, trace_df = allocate_batch(
        students,
        pool,
        policy=policy,
        frames_already_canonical=False,
    )

    logs_en = canonicalize_headers(logs_df, header_mode="en")

    assert allocations_df.empty
    assert logs_en.loc[0, "error_type"] == "ELIGIBILITY_NO_MATCH"
    assert "join_key_mismatches" in logs_en.columns


def test_collect_join_key_map_names_align_with_policy():
    policy = load_policy()

    students = pd.DataFrame(
        [
            {
                "student_id": "S-2",
                "کدرشته": 5,
                "گروه آزمایشی": 5,
                "جنسیت": 0,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            }
        ]
    )

    join_map, missing_columns = _collect_join_key_map(students.iloc[0], policy)

    expected_keys = {_normalize_join_key_name(column) for column in policy.join_keys}

    assert set(join_map.keys()) == expected_keys
    assert missing_columns == ()
    assert all(isinstance(value, int) for value in join_map.values())


def test_allocation_succeeds_when_join_keys_match():
    policy = load_policy()

    students = pd.DataFrame(
        [
            {
                "student_id": "S-3",
                "کدرشته": 3,
                "گروه آزمایشی": 3,
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 0,
            }
        ]
    )

    pool = pd.DataFrame(
        [
            {
                "کد کارمندی پشتیبان": "M-2",
                "پشتیبان": "Mentor Two",
                "کدرشته": 3,
                "گروه آزمایشی": 3,
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 1,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 0,
                "remaining_capacity": 1,
            }
        ]
    )

    allocations_df, _, logs_df, _ = allocate_batch(
        students, pool, policy=policy, frames_already_canonical=False
    )

    logs_en = canonicalize_headers(logs_df, header_mode="en")

    assert len(allocations_df) == 1
    assert logs_en.loc[0, "allocation_status"] == "success"
    assert logs_en.loc[0, "error_type"] is None
