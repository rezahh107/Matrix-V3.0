from __future__ import annotations

import pandas as pd
import pytest

from app.core.matrix.build_matrix_core import build_matrix_core
from app.core.matrix.matrix_schema import JOIN_KEY_COLUMNS, MatrixSchema


def _mentor_row(
    mentor_id: int,
    capacity_limit: int,
    center_code: int,
    school_code: int,
    *,
    allocations_new: int = 0,
) -> dict[str, int]:
    row = {key: 1 for key in JOIN_KEY_COLUMNS}
    row["mentor_id"] = mentor_id
    row["capacity_limit"] = capacity_limit
    row["assigned_baseline"] = 0
    row["allocations_new"] = allocations_new
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
            _mentor_row(101, capacity_limit=3, center_code=10, school_code=30),
            _mentor_row(
                102,
                capacity_limit=2,
                center_code=10,
                school_code=30,
                allocations_new=1,
            ),
            _mentor_row(103, capacity_limit=2, center_code=10, school_code=30),
        ]
    )
    students_df = pd.DataFrame(
        [
            _student_row(201, center_code=10, school_code=30),
            _student_row(202, center_code=10, school_code=30),
        ]
    )

    result = build_matrix_core(mentors_df, students_df, schema=MatrixSchema())

    assert set(result.columns).issuperset({"mentor_id", "student_id", "trace"})
    assert all(column in result.columns for column in MatrixSchema().join_keys)
    expected_rows = len(mentors_df) * len(students_df)
    assert len(result) == expected_rows
    assert result["capacity_ok"].all()
    assert {tuple(trace_step[0] for trace_step in trace[:4]) for trace in result["trace"]} == {
        ("type", "group", "gender", "graduation_status"),
    }
    sorted_result = result.sort_values(
        list(MatrixSchema().ranking_fields), ascending=[False, True, True]
    ).reset_index(drop=True)
    pd.testing.assert_frame_equal(result.reset_index(drop=True), sorted_result)


def test_build_matrix_core_missing_mentor_id_raises() -> None:
    mentor_row = _mentor_row(101, capacity_limit=1, center_code=1, school_code=1)
    del mentor_row["mentor_id"]

    mentors_df = pd.DataFrame([mentor_row])
    students_df = pd.DataFrame([_student_row(201, center_code=1, school_code=1)])

    with pytest.raises(KeyError):
        build_matrix_core(mentors_df, students_df, schema=MatrixSchema())


def test_build_matrix_core_missing_student_id_raises() -> None:
    mentors_df = pd.DataFrame([
        _mentor_row(101, capacity_limit=1, center_code=1, school_code=1)
    ])
    student_row = _student_row(201, center_code=1, school_code=1)
    del student_row["student_id"]

    students_df = pd.DataFrame([student_row])

    with pytest.raises(KeyError):
        build_matrix_core(mentors_df, students_df, schema=MatrixSchema())
