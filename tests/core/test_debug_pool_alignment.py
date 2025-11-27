from __future__ import annotations

import pandas as pd

from app.core.debug_pool_alignment import (
    analyze_pool_alignment_batch,
    analyze_pool_alignment_for_student,
)
from app.core.policy_loader import PolicyConfig, load_policy


def _base_student(policy: PolicyConfig) -> dict[str, int]:
    return {column: 1 for column in policy.join_keys}


def _build_pool(
    policy: PolicyConfig, center_value: int = 1, finance_value: int = 1
) -> pd.DataFrame:
    stage_columns = policy.join_stage_columns
    capacity_column = policy.capacity_column
    data: list[dict[str, int]] = []
    center_column = policy.stage_column("center")
    finance_column = policy.stage_column("finance")
    for _ in range(3):
        row = {column: 1 for column in stage_columns}
        row[center_column] = center_value
        row[finance_column] = finance_value
        row[capacity_column] = 2
        data.append(row)
    return pd.DataFrame(data)


def test_analyzer_happy_path_returns_candidates() -> None:
    policy = load_policy()
    student = {"student_id": "s1", **_base_student(policy)}
    pool = _build_pool(policy)

    report = analyze_pool_alignment_for_student(student, pool, policy=policy)

    assert report["error"] is None
    assert report["candidate_count_initial"] == 3
    assert report["candidate_count_final"] >= 1
    assert not report["join_key_mismatches"]


def test_analyzer_zero_after_finance_stage() -> None:
    policy = load_policy()
    student = {"student_id": "s2", **_base_student(policy)}
    # Ensure the student finance code is outside the policy variant family so the finance
    # stage legitimately removes all candidates.
    student[policy.stage_column("finance")] = 9
    pool = _build_pool(policy, finance_value=0)

    report = analyze_pool_alignment_for_student(student, pool, policy=policy)

    assert report["candidate_count_initial"] == 3
    assert report["stage_counts"]["finance"] == 0
    assert report["candidate_count_final"] == 0


def test_analyzer_reports_join_key_mismatch() -> None:
    policy = load_policy()
    student = {"student_id": "s3", **_base_student(policy)}
    off_center = 999
    student[policy.stage_column("center")] = off_center
    pool = _build_pool(policy, center_value=1)

    report = analyze_pool_alignment_for_student(student, pool, policy=policy)

    assert report["candidate_count_final"] == 0
    assert any(
        detail["column"] == policy.stage_column("center")
        for detail in report["join_key_mismatches"]
    )


def test_batch_analysis_is_deterministic() -> None:
    policy = load_policy()
    student_rows = [
        {"student_id": "b", **_base_student(policy)},
        {"student_id": "a", **_base_student(policy)},
    ]
    students_df = pd.DataFrame(student_rows)
    pool = _build_pool(policy)

    first_run = analyze_pool_alignment_batch(students_df, pool, policy=policy, limit=None)
    second_run = analyze_pool_alignment_batch(students_df, pool, policy=policy, limit=None)

    assert [report["student_id"] for report in first_run] == [
        report["student_id"] for report in second_run
    ]
    assert [report["candidate_count_final"] for report in first_run] == [
        report["candidate_count_final"] for report in second_run
    ]
