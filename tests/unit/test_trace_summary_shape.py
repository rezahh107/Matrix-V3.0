import pandas as pd

from app.core import allocate_students
from app.core.common.types import CANONICAL_TRACE_ORDER
from app.core.policy_loader import load_policy


def test_trace_summary_uses_tracker_counts(monkeypatch: object) -> None:
    policy = load_policy()
    student = pd.DataFrame(
        [
            {
                "student_id": "S-1",
                policy.stage_column("group"): 27,
                policy.stage_column("gender"): 1,
                policy.stage_column("graduation_status"): 0,
                policy.stage_column("center"): 1,
                policy.stage_column("finance"): 0,
                policy.stage_column("school"): 111,
            }
        ]
    )
    pool = pd.DataFrame(
        {
            "پشتیبان": ["M1", "M2", "M3"],
            "کد کارمندی پشتیبان": ["E1", "E2", "E3"],
            policy.stage_column("group"): [27, 27, 27],
            policy.stage_column("gender"): [1, 1, 1],
            policy.stage_column("graduation_status"): [0, 0, 0],
            policy.stage_column("center"): [1, 1, 1],
            policy.stage_column("finance"): [0, 0, 0],
            policy.stage_column("school"): [0, 0, 0],
            "remaining_capacity": [5, 5, 5],
            "allocations_new": [0, 0, 0],
            "occupancy_ratio": [0.1, 0.2, 0.3],
            "mentor_id": [101, 102, 103],
        }
    )

    def fake_apply_join_filters(pool_df, student_row, *, policy, student_join_map=None, tracker=None):
        for stage_name in CANONICAL_TRACE_ORDER[:-1]:
            if tracker:
                tracker(stage_name, pool_df.shape[0])
        return pool_df

    monkeypatch.setattr(allocate_students, "apply_join_filters", fake_apply_join_filters)

    result = allocate_students.allocate_batch(
        student,
        pool,
        policy=policy,
        frames_already_canonical=False,
    )

    trace_df = result.trace_df
    student_trace = trace_df.loc[trace_df["student_id"] == "S-1"]

    assert list(student_trace["stage"]) == list(CANONICAL_TRACE_ORDER)
    totals_before = student_trace["total_before"].tolist()
    totals_after = student_trace["total_after"].tolist()
    stage_counts = result.logs_df.iloc[0]["stage_candidate_counts"]

    assert totals_before[0] == pool.shape[0]
    assert totals_after == [stage_counts[stage] for stage in CANONICAL_TRACE_ORDER]
    for idx in range(1, len(CANONICAL_TRACE_ORDER)):
        assert totals_before[idx] == totals_after[idx - 1]
