from __future__ import annotations

import pandas as pd

from app.core.build_matrix import COL_GROUP_INCLUDED, build_matrix
from app.core.common.domain import BuildConfig
from app.core.qa.invariants import check_MENTOR_TYPE_01


def test_build_matrix_school_expansion_qa_passes() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    inspactor_df = pd.DataFrame(
        {
            "نام پشتیبان": ["mentor-school"],
            "نام مدیر": ["manager"],
            "کد کارمندی پشتیبان": ["S10"],
            "کدپستی": [""],
            "تعداد مدارس تحت پوشش": [2],
            "تعداد داوطلبان تحت پوشش": [5],
            "تعداد تحت پوشش خاص": [0],
            COL_GROUP_INCLUDED: ["3"],
            "گروه آزمایشی": [3],
            "جنسیت": [1],
            "وضعیت تحصیلی": [1],
            "کد مدرسه": [0],
            "نام مدرسه 1": [5001],
            "نام مدرسه 2": [5002],
            "نام مدرسه 3": [0],
            "نام مدرسه 4": [0],
            "امکان جذب دانش آموز": ["Yes"],
        }
    )
    schools_df = pd.DataFrame(
        {"کد مدرسه": [5001, 5002], "نام مدرسه 1": ["مدرسه 1", "مدرسه 2"]}
    )
    crosswalk_df = pd.DataFrame({"گروه آزمایشی": [3], "کد گروه": [3], "مقطع تحصیلی": ["پایه"]})

    matrix, *_ = build_matrix(inspactor_df, schools_df, crosswalk_df, cfg=cfg)

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=cfg.policy)
    assert result.passed
    assert not result.violations
