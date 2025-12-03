from __future__ import annotations

import pandas as pd
import pytest

from app.core.common.join_keys import (
    assert_canonical_join_keys,
    validate_and_canonicalize_join_keys,
)
from app.core.policy_loader import load_policy


def test_validate_and_canonicalize_join_keys_all_valid() -> None:
    policy = load_policy()
    df = pd.DataFrame(
        [
            {
                "کدرشته": "1",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
            {
                "کدرشته": "3",
                "جنسیت": "1",
                "دانش آموز فارغ": "0",
                "مرکز گلستان صدرا": "2",
                "مالی حکمت بنیاد": "1",
                "کد مدرسه": "11",
            },
        ]
    )
    result = validate_and_canonicalize_join_keys(df, policy=policy, entity_type="student")
    assert result.issues == []
    assert len(result.canonical_df) == 2
    for column in policy.join_keys:
        assert pd.api.types.is_integer_dtype(result.canonical_df[column])


def test_validate_and_canonicalize_join_keys_collects_invalid() -> None:
    policy = load_policy()
    df = pd.DataFrame(
        [
            {
                "کدرشته": "",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
            {
                "کدرشته": "abc",
                "جنسیت": "x",
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
        ]
    )
    result = validate_and_canonicalize_join_keys(df, policy=policy, entity_type="student")
    assert len(result.canonical_df) == 0
    assert result.invalid_rows.shape[0] >= 2


def test_assert_canonical_join_keys_rejects_nulls() -> None:
    policy = load_policy()
    df = pd.DataFrame(
        {
            "کدرشته": pd.Series([1, pd.NA], dtype="Int64"),
            "جنسیت": pd.Series([1, 1], dtype="Int64"),
            "دانش آموز فارغ": pd.Series([0, 0], dtype="Int64"),
            "مرکز گلستان صدرا": pd.Series([1, 1], dtype="Int64"),
            "مالی حکمت بنیاد": pd.Series([1, 1], dtype="Int64"),
            "کد مدرسه": pd.Series([1, 1], dtype="Int64"),
        }
    )
    with pytest.raises(ValueError):
        assert_canonical_join_keys(df, policy)


def test_validate_multiple_entity_types_share_api() -> None:
    policy = load_policy()
    df = pd.DataFrame(
        [
            {
                "کدرشته": "1",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
            {
                "کدرشته": "bad",
                "جنسیت": "x",
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
        ]
    )
    student_result = validate_and_canonicalize_join_keys(df, policy=policy, entity_type="student")
    school_result = validate_and_canonicalize_join_keys(df, policy=policy, entity_type="school")
    assert len(student_result.issues) == len(school_result.issues)
