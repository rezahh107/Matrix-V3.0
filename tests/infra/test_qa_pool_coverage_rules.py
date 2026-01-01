from __future__ import annotations

import pandas as pd

from app.core.policy_loader import load_policy
from app.core.qa.invariants import run_all_invariants


def test_pool_coverage_rule_flags_missing_candidates() -> None:
    policy = load_policy()
    preflight = pd.DataFrame(
        [
            {
                "student_id": "s1",
                "candidate_count_final": 0,
                "first_failing_stage": "graduation_status",
                "expected_value": 0,
                "available_values": [1],
                "join_key_values": {
                    "کدرشته": 5,
                    "جنسیت": 1,
                    "دانش آموز فارغ": 0,
                    "مرکز گلستان صدرا": 1,
                    "مالی حکمت بنیاد": 0,
                    "کد مدرسه": 0,
                },
            }
        ]
    )

    report = run_all_invariants(
        policy=policy,
        pool_alignment_preflight=preflight,
        enable_pool_coverage_rules=True,
    )

    violations = report.to_details_frame("QA_RULE_POOL_COVERAGE_01")
    assert not violations.empty
    assert violations.loc[0, "first_failing_stage"] == "graduation_status"


def test_pool_diversity_rule_warns_on_narrow_pool() -> None:
    policy = load_policy()
    allocation_summary = pd.DataFrame(
        {
            "کدرشته": [1, 1],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [1, 1],
        }
    )

    report = run_all_invariants(
        policy=policy,
        allocation_summary=allocation_summary,
        enable_pool_coverage_rules=True,
    )

    warnings = report.to_details_frame("QA_RULE_POOL_DIVERSITY_01")
    assert not warnings.empty
    assert report.passed
