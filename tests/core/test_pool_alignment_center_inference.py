from __future__ import annotations

import pandas as pd

from app.core.debug_pool_alignment import analyze_pool_alignment_for_student
from app.core.policy_loader import PolicyConfig, load_policy
from app.core.qa.invariants import run_all_invariants


def _base_student(policy: PolicyConfig) -> dict[str, int]:
    return {column: 1 for column in policy.join_keys}


def _build_pool(policy: PolicyConfig, *, center_value: int) -> pd.DataFrame:
    stage_columns = policy.join_stage_columns
    capacity_column = policy.capacity_column
    data: list[dict[str, int]] = []
    center_column = policy.stage_column("center")
    for _ in range(2):
        row = {column: 1 for column in stage_columns}
        row[center_column] = center_value
        row[capacity_column] = 2
        data.append(row)
    return pd.DataFrame(data)


def test_pool_alignment_uses_effective_center_in_join_map() -> None:
    policy = load_policy()
    student = {"student_id": "center-1", **_base_student(policy)}
    student[policy.stage_column("center")] = 0
    student["manager_name"] = "شهدخت کشاورز"
    pool = _build_pool(policy, center_value=1)

    report = analyze_pool_alignment_for_student(student, pool, policy=policy)

    assert report["stage_counts"]["center"] > 0
    assert report["candidate_count_final"] > 0

    preflight_df = pd.DataFrame([report])
    qa_report = run_all_invariants(
        policy=policy,
        pool_alignment_preflight=preflight_df,
        enable_pool_coverage_rules=True,
    )

    violations = qa_report.to_details_frame("QA_RULE_POOL_COVERAGE_01")
    assert violations.empty
