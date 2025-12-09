from __future__ import annotations

import pandas as pd

from app.core.allocation.allocation_loop_v3 import run_allocation_loop_v3
from app.core.matrix.matrix_schema import MatrixSchema


def _base_trace() -> tuple[tuple[str, str], ...]:
    return (
        ("type", "math"),
        ("group", "A"),
        ("gender", "male"),
        ("graduation_status", "student"),
        ("center", "1"),
        ("finance", "0"),
        ("school", "10"),
    )


def test_happy_path_single_student_multi_mentors() -> None:
    matrix_core = pd.DataFrame(
        {
            "student_id": [1, 1, 1],
            "mentor_id": [201, 202, 203],
            "capacity_limit": [3, 3, 3],
            "assigned_baseline": [0, 0, 0],
            "remaining_capacity": [1, 3, 3],
            "allocations_new": [0, 1, 0],
            "capacity_ok": [True, True, True],
            "total_allocations": [0, 0, 0],
            "trace": [_base_trace()] * 3,
        }
    )

    allocations, traces = run_allocation_loop_v3(matrix_core)

    assert allocations.to_dict(orient="list") == {"student_id": [1], "mentor_id": [203]}
    assert traces.loc[0, "capacity_gate"] == "ok"
    assert traces.loc[0, "mentor_id"] == 203
    assert list(traces.columns) == ["student_id", "mentor_id", *MatrixSchema().trace_steps]


def test_edge_case_frozen_and_no_capacity() -> None:
    matrix_core = pd.DataFrame(
        {
            "student_id": [2, 2, 2],
            "mentor_id": [300, 301, 302],
            "capacity_limit": [2, 2, 2],
            "assigned_baseline": [0, 0, 0],
            "remaining_capacity": [0, 2, 1],
            "allocations_new": [0, 0, 0],
            "capacity_ok": [True, False, True],
            "total_allocations": [0, 0, 0],
            "trace": [_base_trace()] * 3,
        }
    )

    allocations, traces = run_allocation_loop_v3(matrix_core)

    assert allocations.loc[0, "mentor_id"] == 302
    assert traces.loc[0, "capacity_gate"] == "ok"


def test_failure_case_unmatchable_student() -> None:
    matrix_core = pd.DataFrame(
        {
            "student_id": [3, 3],
            "mentor_id": [400, 401],
            "capacity_limit": [1, 1],
            "assigned_baseline": [0, 0],
            "remaining_capacity": [0, 0],
            "allocations_new": [0, 1],
            "capacity_ok": [False, False],
            "total_allocations": [0, 0],
            "trace": [_base_trace()] * 2,
        }
    )

    allocations, traces = run_allocation_loop_v3(matrix_core)

    assert allocations.loc[0, "mentor_id"] is None
    assert traces.loc[0, "capacity_gate"] == "blocked"
