from __future__ import annotations

import pandas as pd

from app.core.matrix.coverage import compute_group_coverage_debug


def test_coverage_counts_dual_variants_separately() -> None:
    join_keys = ["کدرشته", "جنسیت", "دانش آموز فارغ", "center_code", "مالی حکمت بنیاد", "کد مدرسه"]
    base = pd.DataFrame(
        {
            "group_pairs": [[("ریاضی", 1)]],
            "genders": [[1]],
            "statuses_normal": [[1]],
            "statuses_school": [[1]],
            "finance": [[0]],
            "schools_normal": [[""]],
            "school_codes": [[0]],
            "مرکز گلستان صدرا": [1],
            "center_code": [1],
            "alias_normal": ["1200"],
            "alias_school": ["EMP-1"],
            "can_normal": [True],
            "can_school": [True],
            "mentor_id": ["EMP-1"],
        }
    )
    base.attrs["mentor_pool_governance"] = {"total": len(base), "removed": 0}

    matrix_rows = pd.DataFrame(
        {
            "کدرشته": [1, 1],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [1, 1],
            "center_code": [1, 1],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [0, 0],
            "کد کارمندی پشتیبان": ["EMP-1", "EMP-1"],
        }
    )

    debug, summary = compute_group_coverage_debug(
        matrix_rows,
        base,
        join_keys=join_keys,
        center_column="center_code",
        finance_column="مالی حکمت بنیاد",
        school_code_column="کد مدرسه",
    )

    assert summary["covered_groups"] == 1
    assert set(debug["variant_set"].iloc[0]) == {"normal", "school"}
