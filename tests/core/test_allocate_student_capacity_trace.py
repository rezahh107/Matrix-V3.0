from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pandas as pd

from app.core.allocate_students import allocate_student
from app.core.policy_loader import load_policy


def test_capacity_trace_uses_pool_state_view_counts() -> None:
    policy = load_policy()
    student = {
        "student_id": "s-trace",
        policy.stage_column("group"): 1,
        policy.stage_column("gender"): int(policy.gender_codes.male.value),
        policy.stage_column("graduation_status"): 0,
        policy.stage_column("center"): 10,
        policy.stage_column("finance"): 0,
        policy.columns.school_code: 0,
    }

    candidate_pool = pd.DataFrame(
        {
            "mentor_id": ["m1"],
            policy.stage_column("group"): [1],
            policy.stage_column("gender"): [int(policy.gender_codes.male.value)],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [10],
            policy.stage_column("finance"): [0],
            policy.columns.school_code: [0],
            "remaining_capacity": [1],
            "allocations_new": [0],
            "occupancy_ratio": [0.0],
        }
    )

    pool_state_view = candidate_pool.copy()
    pool_state_view["remaining_capacity"] = [0]

    result = allocate_student(
        student,
        candidate_pool,
        policy=policy,
        pool_state_view=pool_state_view,
    )

    capacity_stage = next(stage for stage in result.trace if stage["stage"] == "capacity_gate")
    extras = cast(Mapping[str, object] | None, capacity_stage.get("extras"))

    assert capacity_stage["total_before"] == 1
    assert capacity_stage["total_after"] == 0
    assert extras is not None and extras.get("capacity_after") == 0
    assert result.log["stage_candidate_counts"]["capacity_gate"] == 0
    assert result.log["allocation_status"] == "failed"
