from __future__ import annotations

import pandas as pd

from app.core.policy_loader import load_policy
from app.core.students.domain_validation import (
    ERROR_INVALID_GRADUATION_FOR_GROUP,
    assert_student_domain_clean,
    validate_student_domain,
)


def test_validate_student_domain_all_valid() -> None:
    policy = load_policy()
    df = pd.DataFrame(
        {
            "کدرشته": [1, 3],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 1],
            "مرکز گلستان صدرا": [1, 1],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [10, 11],
        }
    )
    result = validate_student_domain(df, policy=policy)
    assert result.issues == []
    assert len(result.canonical_df) == 2


def test_validate_student_domain_invalid_graduation_for_group() -> None:
    policy = load_policy()
    df = pd.DataFrame(
        {
            "کدرشته": [33],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [10],
        }
    )
    result = validate_student_domain(df, policy=policy)
    assert len(result.canonical_df) == 0
    assert result.issues[0].error_code == ERROR_INVALID_GRADUATION_FOR_GROUP


def test_assert_student_domain_clean_raises_for_invalid_rows() -> None:
    policy = load_policy()
    df = pd.DataFrame(
        {
            "کدرشته": [27],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [10],
        }
    )
    try:
        assert_student_domain_clean(df, policy=policy)
    except ValueError:
        return
    raise AssertionError("expected ValueError for invalid domain rows")
