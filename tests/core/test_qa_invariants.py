from dataclasses import replace
from typing import Any

import pandas as pd

from app.core.common.domain import StudentBindingKind
from app.core.policy_loader import PolicyConfig, load_policy
from app.core.qa.invariants import QaRuleResult, check_MENTOR_TYPE_01, check_STU_BINDING_01


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
        lambda row, cfg: "unexpected",  # type: ignore[return-value]
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
            "جایگزین": ["1234", "M1"],
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
            "جایگزین": ["1234", "S1"],
            "عادی مدرسه": ["عادی", "مدرسه‌ای"],
            school_col: [0, 10],
        }
    )

    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)

    assert result.passed
    assert not result.violations
