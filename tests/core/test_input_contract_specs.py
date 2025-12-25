from __future__ import annotations

import pandas as pd
import pytest

from app.core.contracts import (
    CrosswalkGroupsSpec,
    InputContractError,
    PoolSpec,
    StudentReportSpec,
)


def test_student_spec_missing_required_column() -> None:
    df = pd.DataFrame({"جنسیت": [1], "دانش آموز فارغ": [0]})

    with pytest.raises(InputContractError) as excinfo:
        StudentReportSpec().validate(df)

    assert "کدرشته" in str(excinfo.value)


def test_crosswalk_groups_spec_missing_group_code() -> None:
    df = pd.DataFrame({"عنوان": ["الف"]})

    with pytest.raises(InputContractError) as excinfo:
        CrosswalkGroupsSpec().validate(df)

    assert "کد گروه" in str(excinfo.value)


def test_pool_spec_required_join_keys_not_null() -> None:
    df = pd.DataFrame(
        {
            "کدرشته": [101],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [11],
            "مالی حکمت بنیاد": [5],
            "کد مدرسه": [None],
        }
    )

    with pytest.raises(InputContractError) as excinfo:
        PoolSpec().validate(df)

    message = str(excinfo.value)
    assert "کد مدرسه" in message
    assert "1" in message or "۱" in message

