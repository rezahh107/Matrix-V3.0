from __future__ import annotations

import pandas as pd

from app.core.allocate_students import _filter_candidates_by_join_map, allocate_student
from app.core.common.join_keys import normalize_join_key_name
from app.core.policy_loader import load_policy


def test_filter_candidates_respects_finance_variants() -> None:
    policy = load_policy()
    join_map = {
        normalize_join_key_name(policy.stage_column("group")): 1,
        normalize_join_key_name(policy.stage_column("gender")): 1,
        normalize_join_key_name(policy.stage_column("graduation_status")): 0,
        normalize_join_key_name(policy.stage_column("center")): 1,
        normalize_join_key_name(policy.stage_column("finance")): 0,
        normalize_join_key_name(policy.columns.school_code): 0,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m2"],
            policy.stage_column("finance"): [1, 3],
            policy.columns.school_code: [0, 0],
            policy.stage_column("center"): [1, 1],
            policy.stage_column("gender"): [1, 1],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("group"): [1, 1],
        }
    )

    filtered, mismatches = _filter_candidates_by_join_map(pool, join_map=join_map, policy=policy)

    assert len(filtered) == 2
    assert not mismatches or all(
        match.get("column") != policy.stage_column("finance") for match in mismatches
    )


def test_join_key_mismatches_preserved_on_success_allocation() -> None:
    policy = load_policy()
    student = {
        "student_id": "s1",
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): 1,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 0,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m2"],
            policy.stage_column("group"): [1, 1],
            policy.stage_column("gender"): [1, 1],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("center"): [1, 1],
            policy.stage_column("finance"): [1, 2],
            policy.columns.school_code: [0, 0],
            "remaining_capacity": [1, 1],
            "allocations_new": [0, 0],
            "occupancy_ratio": [0.0, 0.5],
        }
    )

    result = allocate_student(student, pool, policy=policy)

    assert result.log.get("allocation_status") == "success"
    assert result.log.get("join_key_mismatches")


def test_allocate_student_finance_variants_success() -> None:
    policy = load_policy()
    student = {
        "student_id": "s2",
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): 0,
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 1,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 123,
    }
    pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m2"],
            policy.stage_column("group"): [1, 1],
            policy.stage_column("gender"): [0, 0],
            policy.stage_column("graduation_status"): [0, 0],
            policy.stage_column("center"): [1, 1],
            policy.stage_column("finance"): [
                policy.finance_variants[0],
                policy.finance_variants[1],
            ],
            policy.columns.school_code: [123, 123],
            "remaining_capacity": [1, 1],
            "allocations_new": [0, 0],
            "occupancy_ratio": [0.1, 0.2],
        }
    )

    result = allocate_student(student, pool, policy=policy)

    assert result.log.get("allocation_status") == "success"
    assert result.log.get("mentor_id") == "m1"
