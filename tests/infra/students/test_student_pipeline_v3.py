from __future__ import annotations

import pandas as pd
import pytest

from app.core.common.types import StudentDomainValidationIssue, StudentDomainValidationResult
from app.core.policy_loader import PolicyConfig, load_policy
from app.infra.students import pipeline_v3
from app.infra.students.student_pipeline_v3 import StudentPipelineV3


def _valid_student_frame(policy: PolicyConfig) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "کدرشته": [1],
            "گروه آزمایشی": [1],
            "جنسیت": [policy.gender_codes.male.value],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [1],
            "کد مدرسه": [10],
        }
    )


def test_student_pipeline_v3_happy_path() -> None:
    policy = load_policy()
    pipeline = StudentPipelineV3(policy=policy, reference_mode="excel")
    df = _valid_student_frame(policy)

    result = pipeline.run(df)

    assert result.can_continue
    assert not result.domain_result.issues


def test_student_pipeline_v3_allows_non_blocking_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = load_policy()
    pipeline = StudentPipelineV3(policy=policy, reference_mode="excel")
    df = _valid_student_frame(policy)

    def _fake_domain_validation(df_students: pd.DataFrame, *, policy: object, progress: object = None) -> StudentDomainValidationResult:  # type: ignore[override]
        issue = StudentDomainValidationIssue(
            row_index=0,
            group_code=1,
            graduation_status=0,
            allowed_statuses=(0, 1),
            error_code="P1_TEST_ONLY",
            severity="P1",
        )
        return StudentDomainValidationResult(canonical_df=df_students, issues=[issue])

    monkeypatch.setattr(pipeline_v3, "validate_student_domain", _fake_domain_validation)

    result = pipeline.run(df)

    assert result.can_continue
    assert result.domain_result.issues


def test_student_pipeline_v3_blocks_on_p0_domain_issue() -> None:
    policy = load_policy()
    pipeline = StudentPipelineV3(policy=policy, reference_mode="excel")
    df = _valid_student_frame(policy)
    df.loc[0, "دانش آموز فارغ"] = 99

    result = pipeline.run(df)

    assert not result.can_continue
    assert result.domain_result.issues


def test_student_pipeline_v3_missing_join_key_blocks() -> None:
    policy = load_policy()
    pipeline = StudentPipelineV3(policy=policy, reference_mode="excel")
    df = pd.DataFrame(
        {
            "جنسیت": [policy.gender_codes.male.value],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [1],
            "کد مدرسه": [10],
        }
    )

    result = pipeline.run(df)

    assert not result.can_continue
    assert result.validation.join_keys.issues

