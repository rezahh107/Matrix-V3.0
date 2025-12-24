from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

from app.core.build_matrix import COL_GROUP_INCLUDED, DUAL_STATUS_GROUPS, build_matrix
from app.core.common.domain import (
    STUDENT_ONLY_GROUPS,
    BuildConfig,
    allowed_statuses_for_group,
)
from app.core.policy_loader import load_policy


def test_status_domain_sets_follow_policy_codes() -> None:
    assert frozenset({1, 3, 5, 7, 8, 9, 11, 12, 14, 17, 18}) == DUAL_STATUS_GROUPS
    assert frozenset({33, 31, 27}) == STUDENT_ONLY_GROUPS
    # هنر (7) is dual-status; پایه هفتم (33) is student-only
    assert 7 in DUAL_STATUS_GROUPS
    assert 33 not in DUAL_STATUS_GROUPS


def test_grade_seven_code_is_not_art_code() -> None:
    # کدرشته 7 (هنر کنکوری) می‌تواند فارغ‌التحصیل باشد؛ کدرشته 33 (پایه هفتم) نمی‌تواند
    assert allowed_statuses_for_group(7, is_school_branch=False) == (1, 0)
    assert allowed_statuses_for_group(33, is_school_branch=False) == (1,)
    assert allowed_statuses_for_group(33, is_school_branch=True) == (1,)


def _minimal_crosswalk() -> pd.DataFrame:
    return pd.DataFrame({"گروه آزمایشی": [3], "کد گروه": [3], "مقطع تحصیلی": ["پایه"]})


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
            COL_GROUP_INCLUDED: ["3", "3"],
            "گروه آزمایشی": [3, 3],
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


def test_build_matrix_accepts_policy_override_for_small_postal_alias() -> None:
    cfg = BuildConfig(enable_capacity_gate=False, postal_valid_range=(1, 9999))
    inspactor_df = pd.DataFrame(
        {
            "نام پشتیبان": ["عادی"],
            "نام مدیر": ["مدیر1"],
            "کد کارمندی پشتیبان": ["M1"],
            "کدپستی": ["999"],
            "تعداد مدارس تحت پوشش": [0],
            "تعداد داوطلبان تحت پوشش": [5],
            "تعداد تحت پوشش خاص": [0],
            COL_GROUP_INCLUDED: ["3"],
            "گروه آزمایشی": [3],
            "جنسیت": [1],
            "وضعیت تحصیلی": [1],
            "کد مدرسه": [0],
            "کد مدرسه 1": [0],
            "نام مدرسه 1": [""],
            "امکان جذب دانش آموز": ["Yes"],
        }
    )

    schools_df = pd.DataFrame({"کد مدرسه": [0], "نام مدرسه 1": [""]})
    matrix, *_ = build_matrix(
        inspactor_df,
        schools_df,
        _minimal_crosswalk(),
        cfg=cfg,
    )

    alias_values = set(matrix["جایگزین"].unique())
    assert alias_values == {"999"}
    assert (matrix["عادی مدرسه"] == "عادی").all()


def _policy_with_statuses(normal: list[int], school: list[int]) -> BuildConfig:
    policy = load_policy()
    return BuildConfig(
        enable_capacity_gate=False,
        policy=replace(policy, normal_statuses=normal, school_statuses=school),
    )


def _crosswalk_for_groups() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "گروه آزمایشی": ["dual", "nondual"],
            "کد گروه": [next(iter(DUAL_STATUS_GROUPS)), 27],
            "مقطع تحصیلی": ["پایه", "پایه"],
        }
    )


def _mentor_frame_for_group(
    group_name: str,
    *,
    school_count: int = 0,
    group_code: int | None = None,
) -> pd.DataFrame:
    code = group_name if group_code is None else str(group_code)
    return pd.DataFrame(
        {
            "نام پشتیبان": [f"mentor-{group_name}"],
            "نام مدیر": ["manager"],
            "کد کارمندی پشتیبان": [f"{group_name}-id"],
            "کدپستی": ["5000"],
            "تعداد مدارس تحت پوشش": [school_count],
            "تعداد داوطلبان تحت پوشش": [5],
            "تعداد تحت پوشش خاص": [0],
            COL_GROUP_INCLUDED: [code],
            "گروه آزمایشی": [group_name],
            "جنسیت": [1],
            "وضعیت تحصیلی": [1],
            "کد مدرسه": [0 if school_count == 0 else 5001],
            "کد مدرسه 1": [0 if school_count == 0 else 5001],
            "نام مدرسه 1": ["" if school_count == 0 else "مدرسه"],
            "امکان جذب دانش آموز": ["Yes"],
        }
    )


def _school_inspactor_row(
    *,
    mentor_id: str,
    school_count: int | None,
    school_tokens: list[int | str],
) -> pd.DataFrame:
    tokens = list(school_tokens) + ["", "", "", ""]
    tokens = tokens[:4]
    return pd.DataFrame(
        {
            "نام پشتیبان": [f"mentor-{mentor_id}"],
            "نام مدیر": ["manager"],
            "کد کارمندی پشتیبان": [mentor_id],
            "کدپستی": ["5000"],
            "تعداد مدارس تحت پوشش": ["" if school_count is None else school_count],
            "تعداد داوطلبان تحت پوشش": [5],
            "تعداد تحت پوشش خاص": [0],
            COL_GROUP_INCLUDED: ["3"],
            "گروه آزمایشی": [3],
            "جنسیت": [1],
            "وضعیت تحصیلی": [1],
            "کد مدرسه": [0],
            "کد مدرسه 1": [tokens[0] if tokens[0] != "" else 0],
            "نام مدرسه 1": [tokens[0]],
            "نام مدرسه 2": [tokens[1]],
            "نام مدرسه 3": [tokens[2]],
            "نام مدرسه 4": [tokens[3]],
            "امکان جذب دانش آموز": ["Yes"],
        }
    )


def test_dual_status_group_allows_student_and_graduate() -> None:
    cfg = _policy_with_statuses([1, 0], [1, 0])
    group_code = next(iter(DUAL_STATUS_GROUPS))
    inspactor_df = _mentor_frame_for_group("dual", group_code=group_code)
    schools_df = pd.DataFrame({"کد مدرسه": [0], "نام مدرسه 1": [""]})

    matrix, *_ = build_matrix(
        inspactor_df,
        schools_df,
        _crosswalk_for_groups(),
        cfg=cfg,
    )

    normal_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "dual-id"]
    assert set(normal_rows[cfg.policy.stage_column("graduation_status")].unique()) == {0, 1}


def test_non_dual_group_is_student_only() -> None:
    cfg = _policy_with_statuses([1, 0], [1, 0])
    inspactor_df = _mentor_frame_for_group("nondual", group_code=27)
    schools_df = pd.DataFrame({"کد مدرسه": [0], "نام مدرسه 1": [""]})

    matrix, *_ = build_matrix(
        inspactor_df,
        schools_df,
        _crosswalk_for_groups(),
        cfg=cfg,
    )

    normal_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "nondual-id"]
    assert set(normal_rows[cfg.policy.stage_column("graduation_status")].unique()) == {1}


def test_policy_override_blocks_graduate_for_restricted_groups() -> None:
    cfg = _policy_with_statuses([1, 0], [1, 0])
    restricted_group = next(iter(STUDENT_ONLY_GROUPS))
    inspactor_df = _mentor_frame_for_group("restricted", group_code=restricted_group)
    schools_df = pd.DataFrame({"کد مدرسه": [0], "نام مدرسه 1": [""]})

    matrix, *_ = build_matrix(
        inspactor_df,
        schools_df,
        pd.DataFrame(
            {
                "گروه آزمایشی": ["restricted"],
                "کد گروه": [restricted_group],
                "مقطع تحصیلی": ["پایه"],
            }
        ),
        cfg=cfg,
    )

    normal_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "restricted-id"]
    assert set(normal_rows[cfg.policy.stage_column("graduation_status")].unique()) == {1}


def test_build_matrix_expands_school_tokens_by_count() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    inspactor_df = _school_inspactor_row(
        mentor_id="S1", school_count=2, school_tokens=[5001, 5002, 0, 0]
    )
    schools_df = pd.DataFrame(
        {"کد مدرسه": [5001, 5002], "نام مدرسه 1": ["مدرسه 1", "مدرسه 2"]}
    )

    matrix, *_ = build_matrix(inspactor_df, schools_df, _minimal_crosswalk(), cfg=cfg)

    school_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "S1"]
    assert not school_rows.empty
    assert (school_rows["عادی مدرسه"] == "مدرسه‌ای").all()
    assert set(school_rows[cfg.policy.columns.school_code].unique()) == {5001, 5002}


def test_school_binding_headers_name_family_maps_to_codes() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    inspactor_df = _school_inspactor_row(
        mentor_id="9001",
        school_count=2,
        school_tokens=[5001, 5002, 0, 0],
    )
    inspactor_df = inspactor_df.drop(columns=["کد مدرسه 1"], errors="ignore")
    schools_df = pd.DataFrame(
        {"کد مدرسه": [5001, 5002], "نام مدرسه 1": ["مدرسه 1", "مدرسه 2"]}
    )

    matrix, *_ = build_matrix(inspactor_df, schools_df, _minimal_crosswalk(), cfg=cfg)

    school_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "9001"]
    assert not school_rows.empty
    assert set(school_rows[cfg.policy.columns.school_code].unique()) == {5001, 5002}


def test_school_binding_headers_code_family_works() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    inspactor_df = _school_inspactor_row(
        mentor_id="9002",
        school_count=2,
        school_tokens=[5001, 5002, 0, 0],
    )
    inspactor_df = inspactor_df.drop(
        columns=["نام مدرسه 1", "نام مدرسه 2", "نام مدرسه 3", "نام مدرسه 4"],
        errors="ignore",
    )
    inspactor_df["کد مدرسه 2"] = 5002
    inspactor_df["کد مدرسه 3"] = 0
    inspactor_df["کد مدرسه 4"] = 0
    schools_df = pd.DataFrame(
        {"کد مدرسه": [5001, 5002], "نام مدرسه 1": ["مدرسه 1", "مدرسه 2"]}
    )

    matrix, *_ = build_matrix(inspactor_df, schools_df, _minimal_crosswalk(), cfg=cfg)

    school_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "9002"]
    assert not school_rows.empty
    assert set(school_rows[cfg.policy.columns.school_code].unique()) == {5001, 5002}


def test_school_mentor_missing_codes_fails_fast() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    inspactor_df = _school_inspactor_row(
        mentor_id="S_missing",
        school_count=1,
        school_tokens=[0, 0, 0, 0],
    )
    schools_df = pd.DataFrame({"کد مدرسه": [0], "نام مدرسه 1": [""]})

    with pytest.raises(ValueError) as excinfo:
        build_matrix(inspactor_df, schools_df, _minimal_crosswalk(), cfg=cfg)

    assert getattr(excinfo.value, "is_missing_school_codes_error", False)


def test_build_matrix_missing_required_school_codes_fails() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    inspactor_df = _school_inspactor_row(
        mentor_id="S1", school_count=3, school_tokens=[5001, 5002, 0, 0]
    )
    schools_df = pd.DataFrame(
        {"کد مدرسه": [5001, 5002], "نام مدرسه 1": ["مدرسه 1", "مدرسه 2"]}
    )

    with pytest.raises(ValueError) as excinfo:
        build_matrix(inspactor_df, schools_df, _minimal_crosswalk(), cfg=cfg)

    assert getattr(excinfo.value, "is_missing_school_codes_error", False)
    invalid_df = getattr(excinfo.value, "invalid_mentors_df", pd.DataFrame())
    assert not invalid_df.empty
    assert invalid_df["mentor_id"].iat[0] == "S1"
    assert invalid_df["expected_school_count"].iat[0] == 3
    assert invalid_df["found_school_count"].iat[0] == 2


def test_build_matrix_expands_tokens_when_school_count_missing() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    inspactor_df = _school_inspactor_row(
        mentor_id="S2", school_count=None, school_tokens=[0, 0, 5003, 0]
    )
    schools_df = pd.DataFrame({"کد مدرسه": [5003], "نام مدرسه 1": ["مدرسه 3"]})

    matrix, *_ = build_matrix(inspactor_df, schools_df, _minimal_crosswalk(), cfg=cfg)

    school_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "S2"]
    assert not school_rows.empty
    assert (school_rows["عادی مدرسه"] == "مدرسه‌ای").all()
    assert set(school_rows[cfg.policy.columns.school_code].unique()) == {5003}


def test_build_matrix_non_school_mentor_unchanged() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    inspactor_df = _school_inspactor_row(
        mentor_id="M1", school_count=0, school_tokens=[0, 0, 0, 0]
    )
    schools_df = pd.DataFrame({"کد مدرسه": [0], "نام مدرسه 1": [""]})

    matrix, *_ = build_matrix(inspactor_df, schools_df, _minimal_crosswalk(), cfg=cfg)

    normal_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "M1"]
    assert not normal_rows.empty
    assert (normal_rows["عادی مدرسه"] == "عادی").all()
    assert set(normal_rows[cfg.policy.columns.school_code].unique()) == {0}


def test_build_matrix_preserves_name_columns_in_legacy_path() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    inspactor_df = _school_inspactor_row(
        mentor_id="S_name",
        school_count=1,
        school_tokens=["مدرسه 1", 0, 0, 0],
    )
    inspactor_df = inspactor_df.drop(columns=["کد مدرسه 1"], errors="ignore")
    schools_df = pd.DataFrame({"کد مدرسه": [5001], "نام مدرسه 1": ["مدرسه 1"]})

    matrix, *_ = build_matrix(inspactor_df, schools_df, _minimal_crosswalk(), cfg=cfg)

    school_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "S_name"]
    assert not school_rows.empty
    assert set(school_rows[cfg.policy.columns.school_code].unique()) == {5001}


def test_school_branch_is_always_student_only() -> None:
    cfg = _policy_with_statuses([1, 0], [1, 0])
    group_code = next(iter(DUAL_STATUS_GROUPS))
    inspactor_df = _mentor_frame_for_group("dual", school_count=1, group_code=group_code)
    schools_df = pd.DataFrame({"کد مدرسه": [5001], "نام مدرسه 1": ["مدرسه"]})

    matrix, *_ = build_matrix(
        inspactor_df,
        schools_df,
        _crosswalk_for_groups(),
        cfg=cfg,
    )

    school_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "dual-id"]
    assert set(school_rows[cfg.policy.stage_column("graduation_status")].unique()) == {1}
