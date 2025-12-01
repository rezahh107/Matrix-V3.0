from __future__ import annotations

import pandas as pd

from app.core.build_matrix import build_matrix
from app.core.common.domain import BuildConfig


def _minimal_crosswalk() -> pd.DataFrame:
    return pd.DataFrame({"گروه آزمایشی": ["تجربی"], "کد گروه": [101], "مقطع تحصیلی": ["پایه"]})


def test_build_matrix_uses_mentor_type_rules() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    inspactor_df = pd.DataFrame(
        {
            "نام پشتیبان": ["عادی", "مدرسه"],
            "نام مدیر": ["مدیر1", "مدیر2"],
            "کد کارمندی پشتیبان": ["M1", "S1"],
            "کدپستی": ["5000", ""],
            "تعداد مدارس تحت پوشش": [0, 1],
            "تعداد داوطلبان تحت پوشش": [5, 5],
            "تعداد تحت پوشش خاص": [0, 0],
            "گروه آزمایشی": ["تجربی", "تجربی"],
            "جنسیت": [1, 1],
            "وضعیت تحصیلی": [1, 1],
            "کد مدرسه": [0, 5001],
            "کد مدرسه 1": [0, 5001],
            "نام مدرسه 1": ["", "مدرسه"],
            "امکان جذب دانش آموز": ["Yes", "Yes"],
        }
    )

    schools_df = pd.DataFrame({"کد مدرسه": [5001], "نام مدرسه 1": ["مدرسه"]})
    matrix, *_ = build_matrix(
        inspactor_df,
        schools_df,
        _minimal_crosswalk(),
        cfg=cfg,
    )

    normal_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "M1"]
    assert not normal_rows.empty
    assert (normal_rows["عادی مدرسه"] == "عادی").all()
    assert set(normal_rows[cfg.policy.columns.school_code].unique()) == {0}
    assert set(normal_rows["جایگزین"].unique()) == {"5000"}

    school_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "S1"]
    assert not school_rows.empty
    assert (school_rows["عادی مدرسه"] == "مدرسه‌ای").all()
    assert set(school_rows[cfg.policy.columns.school_code].unique()) == {5001}
    assert set(school_rows["جایگزین"].unique()) == {"S1"}
