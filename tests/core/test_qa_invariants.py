from __future__ import annotations

from dataclasses import replace
from typing import Any

import pandas as pd

from app.core.build_matrix import DUAL_STATUS_GROUPS
from app.core.common.domain import COL_MENTOR_TYPE, STUDENT_ONLY_GROUPS, StudentBindingKind
from app.core.policy_loader import PolicyConfig, load_policy
from app.core.qa.invariants import (
    QaRuleResult,
    check_MENTOR_TYPE_01,
    check_STATUS_DOMAIN_01,
    check_STU_BINDING_01,
)


def _policy_with_school_codes() -> PolicyConfig:
    policy = load_policy()
    return replace(
        policy, allocation_channels=replace(policy.allocation_channels, school_codes=(10,))
    )


def test_student_binding_invariant_requires_columns() -> None:
    policy = _policy_with_school_codes()
    student_report = pd.DataFrame({policy.columns.school_code: [10]})

    result = check_STU_BINDING_01(student_report=student_report, policy=policy)

    assert isinstance(result, QaRuleResult)
    assert not result.passed
    assert result.violations and result.violations[0].rule_id == "QA_RULE_STU_BINDING_01"


def test_student_binding_invariant_passes_for_school_students() -> None:
    policy = _policy_with_school_codes()
    status_col = policy.stage_column("graduation_status")
    student_report = pd.DataFrame(
        {
            policy.columns.school_code: [10, 0],
            status_col: [1, 0],
        }
    )

    result = check_STU_BINDING_01(student_report=student_report, policy=policy)

    assert result.passed
    assert not result.violations


def test_student_binding_invariant_blocks_legacy(monkeypatch: Any) -> None:
    policy = _policy_with_school_codes()
    status_col = policy.stage_column("graduation_status")
    student_report = pd.DataFrame({policy.columns.school_code: [10], status_col: [1]})

    monkeypatch.setattr(
        "app.core.qa.invariants.classify_student_binding",
        lambda row, cfg: StudentBindingKind.MENTOR_BASED,
    )

    result = check_STU_BINDING_01(student_report=student_report, policy=policy)

    assert not result.passed
    assert result.violations
    assert result.violations[0].rule_id == "QA_RULE_STU_BINDING_01"


def test_student_binding_invariant_blocks_invalid_value(monkeypatch: Any) -> None:
    policy = _policy_with_school_codes()
    status_col = policy.stage_column("graduation_status")
    student_report = pd.DataFrame({policy.columns.school_code: [10], status_col: [1]})

    monkeypatch.setattr(
        "app.core.qa.invariants.classify_student_binding",
        lambda row, cfg: "unexpected",
    )

    result = check_STU_BINDING_01(student_report=student_report, policy=policy)

    assert not result.passed
    assert result.violations
    assert result.violations[0].rule_id == "QA_RULE_STU_BINDING_01"


def test_mentor_type_invariant_blocks_dual_rows() -> None:
    policy = _policy_with_school_codes()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "کد کارمندی پشتیبان": ["M1", "M1"],
            "جایگزین": ["5000", "M1"],
            "عادی مدرسه": ["عادی", "مدرسه‌ای"],
            school_col: [0, 10],
        }
    )

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)

    assert not result.passed
    assert result.violations
    assert result.violations[0].rule_id == "QA_RULE_MENTOR_TYPE_01"


def test_mentor_type_invariant_validates_alias_and_school_code() -> None:
    policy = _policy_with_school_codes()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "کد کارمندی پشتیبان": ["M1", "S1"],
            "جایگزین": ["5000", "S1"],
            "عادی مدرسه": ["عادی", "مدرسه‌ای"],
            school_col: [0, 10],
        }
    )

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)

    assert result.passed
    assert not result.violations


def test_mentor_type_invariant_detects_normal_with_school_code() -> None:
    policy = _policy_with_school_codes()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "کد کارمندی پشتیبان": ["M1"],
            "جایگزین": ["5000"],
            "عادی مدرسه": ["عادی"],
            school_col: [10],
        }
    )

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)

    assert not result.passed
    assert result.violations


def test_mentor_type_invariant_detects_school_alias_or_code_errors() -> None:
    policy = _policy_with_school_codes()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "کد کارمندی پشتیبان": ["S1", "S2"],
            "جایگزین": ["S1", "wrong"],
            "عادی مدرسه": ["مدرسه‌ای", "مدرسه‌ای"],
            school_col: [0, 10],
        }
    )

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)

    assert not result.passed
    assert result.violations


def test_mentor_type_invariant_reports_missing_school_code_offenders() -> None:
    policy = _policy_with_school_codes()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "کد کارمندی پشتیبان": ["S2", "S1"],
            "جایگزین": ["S2", "S1"],
            "عادی مدرسه": ["مدرسه‌ای", "مدرسه‌ای"],
            school_col: [pd.NA, 0],
            "source_sheet": ["SheetB", "SheetA"],
            "source_row_index": [5, 2],
        }
    )

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)

    assert not result.passed
    violation = next(
        item
        for item in result.violations
        if item.message == "سطر مدرسه‌ای بدون کد مدرسه معتبر"
    )
    offenders = violation.details["offenders"]
    assert isinstance(offenders, list)
    assert offenders[0]["source_sheet"] == "SheetA"
    assert offenders[0]["source_row_index"] == 2
    assert offenders[0]["mentor_id"] == "S1"
    assert offenders[0]["mentor_type"] == "مدرسه‌ای"
    assert offenders[0]["resolved_school_code"] == 0
    assert offenders[0]["reason"] == "MISSING_SCHOOL_CODE"


def test_mentor_type_invariant_accepts_school_rows_with_valid_code() -> None:
    policy = _policy_with_school_codes()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "کد کارمندی پشتیبان": ["S1"],
            "جایگزین": ["S1"],
            "عادی مدرسه": ["مدرسه‌ای"],
            school_col: [10],
        }
    )

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)

    assert result.passed
    assert not result.violations


def test_mentor_type_invariant_allows_normal_missing_school_code() -> None:
    policy = _policy_with_school_codes()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "کد کارمندی پشتیبان": ["M1"],
            "جایگزین": ["5000"],
            "عادی مدرسه": ["عادی"],
            school_col: [pd.NA],
        }
    )

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)

    assert result.passed
    assert not result.violations


def test_mentor_type_invariant_accepts_small_postal_within_policy_range() -> None:
    policy = replace(_policy_with_school_codes(), postal_valid_range=(1, 9999))
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "کد کارمندی پشتیبان": ["M1"],
            "جایگزین": ["999"],
            "عادی مدرسه": ["عادی"],
            school_col: [0],
        }
    )

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)

    assert result.passed
    assert not result.violations


def test_status_domain_invariant_accepts_dual_group() -> None:
    policy = _policy_with_school_codes()
    group_col = policy.stage_column("type")
    status_col = policy.stage_column("graduation_status")
    dual_group = next(iter(DUAL_STATUS_GROUPS))

    matrix = pd.DataFrame(
        {
            group_col: [dual_group, dual_group],
            status_col: [1, 0],
            COL_MENTOR_TYPE: ["عادی", "عادی"],
        }
    )

    result = check_STATUS_DOMAIN_01(matrix=matrix, policy=policy)

    assert result.passed
    assert not result.violations


def test_status_domain_invariant_blocks_non_dual_graduate() -> None:
    policy = _policy_with_school_codes()
    group_col = policy.stage_column("type")
    status_col = policy.stage_column("graduation_status")

    matrix = pd.DataFrame(
        {
            group_col: [27],
            status_col: [0],
            COL_MENTOR_TYPE: ["عادی"],
        }
    )

    result = check_STATUS_DOMAIN_01(matrix=matrix, policy=policy)

    assert not result.passed
    assert result.violations
    assert result.violations[0].rule_id == "QA_RULE_STATUS_DOMAIN_01"


def test_status_domain_invariant_blocks_restricted_graduate() -> None:
    policy = _policy_with_school_codes()
    group_col = policy.stage_column("type")
    status_col = policy.stage_column("graduation_status")

    restricted_group = next(iter(STUDENT_ONLY_GROUPS))
    matrix = pd.DataFrame(
        {
            group_col: [restricted_group],
            status_col: [0],
            COL_MENTOR_TYPE: ["عادی"],
        }
    )

    result = check_STATUS_DOMAIN_01(matrix=matrix, policy=policy)

    assert not result.passed
    assert result.violations
    assert result.violations[0].rule_id == "QA_RULE_STATUS_DOMAIN_01"


def test_status_domain_invariant_blocks_school_graduate() -> None:
    policy = _policy_with_school_codes()
    group_col = policy.stage_column("type")
    status_col = policy.stage_column("graduation_status")

    matrix = pd.DataFrame(
        {
            group_col: [next(iter(DUAL_STATUS_GROUPS))],
            status_col: [0],
            COL_MENTOR_TYPE: ["مدرسه‌ای"],
        }
    )

    result = check_STATUS_DOMAIN_01(matrix=matrix, policy=policy)

    assert not result.passed
    assert result.violations
