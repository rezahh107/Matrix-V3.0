from __future__ import annotations

import pandas as pd

from app.core.matrix.build_matrix_core import build_matrix_core
from app.core.matrix.matrix_schema import JOIN_KEY_COLUMNS, MatrixSchema


def _mentor_row(
    mentor_id: int, capacity_limit: int, center_code: int, school_code: int
) -> dict[str, int]:
    row = {key: 1 for key in JOIN_KEY_COLUMNS}
    row["mentor_id"] = mentor_id
    row["capacity_limit"] = capacity_limit
    row["assigned_baseline"] = 0
    row["allocations_new"] = 0
    row["center_code"] = center_code
    row["school_code"] = school_code
    return row


def _student_row(student_id: int, center_code: int, school_code: int) -> dict[str, int]:
    row = {key: 1 for key in JOIN_KEY_COLUMNS}
    row["student_id"] = student_id
    row["center_code"] = center_code
    row["school_code"] = school_code
    return row


def test_end_to_end_matrix_build() -> None:
    mentors_df = pd.DataFrame(
        [
            _mentor_row(101, capacity_limit=2, center_code=10, school_code=30),
            _mentor_row(102, capacity_limit=0, center_code=11, school_code=31),
        ]
    )
    students_df = pd.DataFrame(
        [
            _student_row(201, center_code=10, school_code=30),
            _student_row(202, center_code=99, school_code=99),
        ]
    )

    result = build_matrix_core(mentors_df, students_df, schema=MatrixSchema())

    assert set(result.columns).issuperset({"mentor_id", "student_id", "trace"})
    assert all(column in result.columns for column in MatrixSchema().join_keys)
    assert (result["capacity_ok"].sum()) == 1
    assert {tuple(trace_step[0] for trace_step in trace[:4]) for trace in result["trace"]} == {
        ("type", "group", "gender", "graduation_status"),
    }
    assert list(result["mentor_id"]) == sorted(result["mentor_id"].tolist())
    assert (result["remaining_capacity"].iloc[0]) >= result["remaining_capacity"].iloc[-1]
