from __future__ import annotations

import pandas as pd
import pytest

from app.core.common.domain import BuildConfig
from app.infra import cli_legacy
from app.infra.mentors.field_registry import FieldRegistry
from app.infra.mentors.header_resolver import HeaderResolver


def _minimal_crosswalk() -> pd.DataFrame:
    return pd.DataFrame({"گروه آزمایشی": [3], "کد گروه": [3], "مقطع تحصیلی": ["پایه"]})


def _base_inspactor_row(*, mentor_id: str, school_count: int | None) -> dict[str, object]:
    return {
        "نام پشتیبان": [f"mentor-{mentor_id}"],
        "نام مدیر": ["manager"],
        "کد کارمندی پشتیبان": [mentor_id],
        "کدپستی": ["5000"],
        "تعداد مدارس تحت پوشش": ["" if school_count is None else school_count],
        "تعداد داوطلبان تحت پوشش": [5],
        "تعداد تحت پوشش خاص": [0],
        "شامل گروه های آزمایشی": ["3"],
        "گروه آزمایشی": [3],
        "کدرشته": [3],
        "جنسیت": [1],
        "دانش آموز فارغ": [1],
        "مرکز گلستان صدرا": [0],
        "مالی حکمت بنیاد": [0],
        "کد مدرسه": [0],
    }


def _schools_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"کد مدرسه": [5001, 5002], "نام مدرسه 1": ["مدرسه 1", "مدرسه 2"]}
    )


def test_v3_name_family_only_builds_matrix() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    row = _base_inspactor_row(mentor_id="9001", school_count=2)
    row.update(
        {
            "نام مدرسه 1": [5001],
            "نام مدرسه 2": [5002],
            "نام مدرسه 3": [0],
            "نام مدرسه 4": [0],
        }
    )
    insp_df = pd.DataFrame(row)

    matrix, *_ = cli_legacy.build_matrix_v3(
        insp_df,
        _schools_df(),
        _minimal_crosswalk(),
        cfg=cfg,
        progress=lambda *_: None,
    )

    school_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "9001"]
    assert set(school_rows[cfg.policy.columns.school_code].unique()) == {5001, 5002}


def test_v3_code_family_only_builds_matrix() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    row = _base_inspactor_row(mentor_id="9002", school_count=2)
    row.update(
        {
            "کد مدرسه 1": [5001],
            "کد مدرسه 2": [5002],
            "کد مدرسه 3": [0],
            "کد مدرسه 4": [0],
        }
    )
    insp_df = pd.DataFrame(row)

    matrix, *_ = cli_legacy.build_matrix_v3(
        insp_df,
        _schools_df(),
        _minimal_crosswalk(),
        cfg=cfg,
        progress=lambda *_: None,
    )

    school_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "9002"]
    assert set(school_rows[cfg.policy.columns.school_code].unique()) == {5001, 5002}


def test_v3_both_families_identical_succeeds() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    row = _base_inspactor_row(mentor_id="9003", school_count=1)
    row.update(
        {
            "نام مدرسه 1": [5001],
            "کد مدرسه 1": [5001],
            "نام مدرسه 2": [0],
            "کد مدرسه 2": [0],
        }
    )
    insp_df = pd.DataFrame(row)

    matrix, *_ = cli_legacy.build_matrix_v3(
        insp_df,
        _schools_df(),
        _minimal_crosswalk(),
        cfg=cfg,
        progress=lambda *_: None,
    )

    school_rows = matrix.loc[matrix["کد کارمندی پشتیبان"] == "9003"]
    assert set(school_rows[cfg.policy.columns.school_code].unique()) == {5001}


def test_v3_both_families_conflict_blocks() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    row = _base_inspactor_row(mentor_id="9004", school_count=1)
    row.update({"نام مدرسه 1": [5002], "کد مدرسه 1": [5001]})
    insp_df = pd.DataFrame(row)

    registry = FieldRegistry(cfg.policy)
    header_result = HeaderResolver(registry).resolve(insp_df)

    assert not header_result.can_continue
    assert any(issue.message == "SCHOOL_BINDING_CONFLICT" for issue in header_result.issues)

    with pytest.raises(ValueError) as excinfo:
        cli_legacy.build_matrix_v3(
            insp_df,
            _schools_df(),
            _minimal_crosswalk(),
            cfg=cfg,
            progress=lambda *_: None,
        )
    assert getattr(excinfo.value, "header_issues", None)


def test_v3_missing_school_codes_fails() -> None:
    cfg = BuildConfig(enable_capacity_gate=False)
    row = _base_inspactor_row(mentor_id="9005", school_count=1)
    row.update(
        {
            "نام مدرسه 1": [0],
            "نام مدرسه 2": [0],
            "نام مدرسه 3": [0],
            "نام مدرسه 4": [0],
        }
    )
    insp_df = pd.DataFrame(row)

    with pytest.raises(ValueError) as excinfo:
        cli_legacy.build_matrix_v3(
            insp_df,
            _schools_df(),
            _minimal_crosswalk(),
            cfg=cfg,
            progress=lambda *_: None,
        )

    assert getattr(excinfo.value, "is_missing_school_codes_error", False)
