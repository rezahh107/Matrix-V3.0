from __future__ import annotations

import pandas as pd
from pytest import MonkeyPatch

from app.core import allocate_students as alloc_mod
from app.core.allocate_students import AllocationResult, allocate_student
from app.core.policy_loader import load_policy


def _base_join_keys(policy: object) -> dict[str, int]:
    config = load_policy() if not hasattr(policy, "join_keys") else policy
    base = {key: 1 for key in config.join_keys}
    group_code_col = config.stage_column("type")
    base[group_code_col] = 27
    return base


def test_allocate_student_preconsume_validation_success() -> None:
    policy = load_policy()
    student = {"student_id": 1}
    student.update(_base_join_keys(policy))
    student[policy.columns.school_code] = 101
    student[policy.stage_column("group")] = 27

    candidate_pool = pd.DataFrame(
        {
            "mentor_id": [10],
            "کد کارمندی پشتیبان": [10],
            "remaining_capacity": [1],
            "allocations_new": [0],
            "occupancy_ratio": [0.0],
        }
    )
    for key, value in student.items():
        if key in policy.join_keys:
            candidate_pool[key] = value
    candidate_pool[policy.stage_column("group")] = student[policy.stage_column("group")]

    result: AllocationResult = allocate_student(
        student, candidate_pool, policy=policy, pool_state_view=candidate_pool
    )

    assert result.log.get("allocation_status") == "success"
    assert not result.log.get("data_corruption_detected", False)


def test_allocate_student_preconsume_validation_catches_conflict(
    monkeypatch: MonkeyPatch,
) -> None:
    policy = load_policy()
    student = {"student_id": 2}
    student.update(_base_join_keys(policy))
    student[policy.columns.school_code] = 202
    student[policy.stage_column("group")] = 27

    conflicting_pool = pd.DataFrame(
        {
            "mentor_id": [99],
            "کد کارمندی پشتیبان": [99],
            "remaining_capacity": [1],
            "allocations_new": [0],
            "occupancy_ratio": [0.0],
        }
    )
    for key in policy.join_keys:
        conflicting_pool[key] = 0
    conflicting_pool[policy.stage_column("group")] = 27

    def _fake_apply_eligibility(pool, *_args, **_kwargs):
        priority = pd.Series(0, index=pool.index, dtype=int)
        return pool, priority, {"stage_counts": {}}

    monkeypatch.setattr(alloc_mod, "apply_eligibility", _fake_apply_eligibility)
    monkeypatch.setattr(
        alloc_mod,
        "_filter_candidates_by_join_map",
        lambda pool, **_kwargs: (pool, []),
    )

    result = allocate_student(
        student, conflicting_pool, policy=policy, pool_state_view=conflicting_pool
    )

    assert result.log.get("allocation_status") == "failed"
    assert result.log.get("error_type") == "INTERNAL_ERROR"
    assert result.log.get("validation_stage") == "pre_consume"
    assert result.log.get("data_corruption_detected") is True
    mismatches = result.log.get("join_key_mismatches")
    assert isinstance(mismatches, list) and mismatches
