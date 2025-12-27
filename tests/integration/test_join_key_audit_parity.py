from __future__ import annotations

import pandas as pd

from app.core.allocate_students import allocate_batch
from app.core.policy_loader import load_policy
from app.infra.cli import _sanitize_pool_for_allocation
from app.infra.qa.alloc_join_validation import validate_allocation_join_keys_with_wildcard


def test_allocation_and_audit_join_key_parity() -> None:
    policy = load_policy()
    students = pd.DataFrame(
        [
            {
                "student_id": "STD-1",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": policy.gender_codes.female.value,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 5,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 2001,
            },
        ]
    )
    pool_raw = pd.DataFrame(
        [
            {
                "mentor_name": "منتور الف",
                "alias": 101,
                "remaining_capacity": 1,
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": policy.gender_codes.female.value,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 0,
                "کد کارمندی پشتیبان": 101,
            }
        ]
    )

    pool = _sanitize_pool_for_allocation(pool_raw, policy=policy)

    allocations, _, _, _ = allocate_batch(students, pool, policy=policy)

    assert allocations.shape[0] == 1
    audit = validate_allocation_join_keys_with_wildcard(
        allocations,
        students,
        pool,
        policy=policy,
    )

    audit_frame = audit.audit_frame
    match_columns = [f"match_{key}" for key in policy.join_keys]
    mentor_columns = [f"{key}_mentor" for key in policy.join_keys]

    assert audit.invalid_count == 0
    expected_columns = set(policy.join_keys) | set(mentor_columns) | set(match_columns)
    assert expected_columns.issubset(audit_frame.columns)
    assert audit_frame[match_columns].all(axis=1).all()
