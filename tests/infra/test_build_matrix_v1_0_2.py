from __future__ import annotations

import pandas as pd

from app.infra.matrix import build_matrix_v1_0_2 as matrix_builder


def test_allowed_statuses_for_group_dual_and_student_only() -> None:
    expected_dual = {1, 3, 5, 7, 8, 9, 11, 12, 14, 17, 18}
    expected_student_only = {
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        29,
        30,
        31,
        33,
        35,
        41,
        43,
        45,
        46,
        53,
        55,
        66,
        69,
        83,
        89,
    }

    assert expected_dual == matrix_builder.DUAL_STATUS_GROUPS

    for code in expected_dual:
        assert list(matrix_builder.allowed_statuses_for_group(code, is_school_branch=False)) == [
            1,
            0,
        ]

    for code in expected_student_only:
        assert list(matrix_builder.allowed_statuses_for_group(code, is_school_branch=False)) == [
            1,
        ]

    assert list(matrix_builder.allowed_statuses_for_group(1, is_school_branch=True)) == [1]


def test_matrix_respects_group_specific_statuses() -> None:
    base = pd.DataFrame(
        {
            "کدرشته": [1, 21, 1],
            "جنسیت": [1, 1, 0],
            "مرکز گلستان صدرا": [10, 10, 11],
            "مالی حکمت بنیاد": [0, 0, 1],
            "کد مدرسه": [0, 0, 1234],
            "عادی مدرسه": ["عادی", "عادی", "مدرسه‌ای"],
        }
    )

    matrix = matrix_builder.build_matrix_v1_0_2(base)

    normal_dual = matrix["کدرشته"].eq(1) & matrix["عادی مدرسه"].eq("عادی")
    school_rows = matrix["عادی مدرسه"].eq("مدرسه‌ای")
    student_only = matrix["کدرشته"].eq(21)

    assert set(matrix.loc[normal_dual, "دانش آموز فارغ"].unique()) == {1, 0}
    assert set(matrix.loc[student_only, "دانش آموز فارغ"].unique()) == {1}
    assert set(matrix.loc[school_rows, "دانش آموز فارغ"].unique()) == {1}

    for key in (
        "کدرشته",
        "جنسیت",
        "دانش آموز فارغ",
        "مرکز گلستان صدرا",
        "مالی حکمت بنیاد",
        "کد مدرسه",
    ):
        assert pd.api.types.is_integer_dtype(matrix[key])
        assert matrix[key].notna().all()

    unique_codes = matrix["کدرشته"].unique()
    for code in unique_codes:
        statuses = set(matrix.loc[matrix["کدرشته"].eq(code), "دانش آموز فارغ"].unique())
        assert statuses <= {0, 1}
        if code in matrix_builder.DUAL_STATUS_GROUPS:
            assert statuses == {0, 1}
        else:
            assert statuses == {1}
