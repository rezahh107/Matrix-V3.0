import pandas as pd

from app.core.allocate_students import allocate_batch
from app.core.common.types import CANONICAL_TRACE_ORDER
from app.core.policy_loader import load_policy


def test_trace_summary_present_for_successful_allocation() -> None:
    policy = load_policy()
    students = pd.DataFrame(
        [
            {
                "student_id": "S-OK",
                policy.stage_column("group"): 5,
                policy.stage_column("gender"): 1,
                policy.stage_column("graduation_status"): 0,
                policy.stage_column("center"): 1,
                policy.stage_column("finance"): 0,
                policy.stage_column("school"): 0,
            }
        ]
    )

    pool = pd.DataFrame(
        {
            "پشتیبان": ["M-OK"],
            "کد کارمندی پشتیبان": ["EMP-OK"],
            policy.stage_column("group"): [5],
            policy.stage_column("gender"): [1],
            policy.stage_column("graduation_status"): [0],
            policy.stage_column("center"): [1],
            policy.stage_column("finance"): [0],
            policy.stage_column("school"): [0],
            "remaining_capacity": [2],
            "allocations_new": [0],
            "occupancy_ratio": [0.0],
            "mentor_id": [999],
        }
    )

    result = allocate_batch(students, pool, policy=policy, frames_already_canonical=False)

    trace_df = result.trace_df
    assert not trace_df.empty

    student_trace = trace_df.loc[trace_df["student_id"] == "S-OK"]
    assert len(student_trace) == len(CANONICAL_TRACE_ORDER)
    assert list(student_trace["stage"]) == list(CANONICAL_TRACE_ORDER)

    summary_df = result.trace_extras.summary_df
    assert summary_df is not None
    assert not summary_df.empty
