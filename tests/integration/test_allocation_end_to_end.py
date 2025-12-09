from __future__ import annotations

import pandas as pd

from app.core.allocation.allocation_loop_v3 import run_allocation_loop_v3


def test_allocation_loop_updates_capacity_across_students() -> None:
    matrix_core = pd.DataFrame(
        {
            "student_id": [10, 11, 11],
            "mentor_id": [500, 500, 501],
            "capacity_limit": [1, 1, 2],
            "assigned_baseline": [0, 0, 0],
            "remaining_capacity": [1, 1, 2],
            "allocations_new": [0, 0, 0],
            "capacity_ok": [True, True, True],
            "total_allocations": [0, 0, 0],
            "trace": [(), (), ()],
        }
    )

    allocations, traces = run_allocation_loop_v3(matrix_core)

    assert allocations.to_dict(orient="list") == {
        "student_id": [10, 11],
        "mentor_id": [500, 501],
    }
    assert traces.loc[0, "capacity_gate"] == "ok"
    assert traces.loc[1, "capacity_gate"] == "ok"
