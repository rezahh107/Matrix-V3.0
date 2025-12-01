from dataclasses import replace

import pandas as pd

from app.core.build_matrix import validate_with_students
from app.core.common.domain import BuildConfig, StudentBindingKind
from app.core.policy_loader import load_policy


def _policy_with_school() -> BuildConfig:
    policy = load_policy()
    tuned_policy = replace(
        policy, allocation_channels=replace(policy.allocation_channels, school_codes=(10,))
    )
    return BuildConfig(policy=tuned_policy, center_map={"*": 0})


def test_validate_with_students_uses_school_binding_over_postal() -> None:
    cfg = _policy_with_school()
    policy = cfg.policy
    center_col = policy.stage_column("center")
    group_col = policy.join_keys[0]
    school_col = policy.columns.school_code

    matrix_df = pd.DataFrame(
        {
            "جایگزین": ["1234", "2000"],
            "عادی مدرسه": ["عادی", "مدرسه‌ای"],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [1, 1],
            center_col: [0, 0],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [0, 10],
            group_col: [101, 101],
        }
    )

    students_df = pd.DataFrame(
        {
            "نام پشتیبان": ["mentor"],
            "مدیر": ["manager"],
            "کد پستی": ["1234"],
            "کد رشته": [101],
            "کد مدرسه 1": ["مدرسه تست"],
            school_col: [10],
        }
    )

    schools_df = pd.DataFrame({"کد مدرسه": [10], "نام مدرسه 1": ["مدرسه تست"]})
    crosswalk_groups_df = pd.DataFrame(
        {"گروه آزمایشی": ["گروه"], "کد گروه": [101], "مقطع تحصیلی": ["پایه"]}
    )

    stud, breakdown, summary = validate_with_students(
        students_df,
        matrix_df,
        schools_df,
        crosswalk_groups_df,
        cfg=cfg,
    )

    assert summary["matched"] == 1
    assert breakdown.set_index("reason").loc["MATCHED", "count"] == 1
    assert stud["student_binding"].iat[0] is StudentBindingKind.SCHOOL
    assert stud["reason"].iat[0] == "MATCHED"
