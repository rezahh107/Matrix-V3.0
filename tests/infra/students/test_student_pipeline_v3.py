from __future__ import annotations

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.students.student_pipeline_v3 import StudentPipelineV3


def test_student_pipeline_v3_happy_path() -> None:
    policy = load_policy()
    pipeline = StudentPipelineV3(policy=policy, reference_mode="excel")
    df = pd.DataFrame(
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

    result = pipeline.run(df)

    assert result.can_continue
    assert len(result.canonical_df) == 1
    assert result.domain_result.issues == []


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

