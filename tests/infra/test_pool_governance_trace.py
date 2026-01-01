from __future__ import annotations

import pandas as pd

from app.core.allocation.mentor_pool import apply_mentor_pool_governance
from app.core.common.types import CANONICAL_JOIN_KEYS
from app.core.policy_loader import load_policy


def test_pool_governance_trace_breakdown_sums() -> None:
    policy = load_policy()
    pool = pd.DataFrame(
        {
            "mentor_id": [1, 1, 2],
            "remaining_capacity": [1, 0, 2],
            **{key: [1, 1, 1] for key in CANONICAL_JOIN_KEYS},
        }
    )

    governed = apply_mentor_pool_governance(
        pool,
        policy.mentor_pool_governance,
        enable_trace=True,
    )

    trace = governed.attrs.get("mentor_pool_governance_trace")
    assert isinstance(trace, list)
    assert trace, "governance trace should include stage entries"

    for entry in trace:
        breakdown = entry.get("removed_breakdown", {})
        removed_rows = int(entry.get("removed_rows", 0))
        total_breakdown = sum(int(value) for value in breakdown.values())
        assert removed_rows == total_breakdown

    first_entry = trace[0]
    assert "group_code" in first_entry.get("distribution_before", {})
