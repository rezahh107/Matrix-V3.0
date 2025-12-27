from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import cast

import pandas as pd

from app.core.matrix.capacity_gates import CapacityOutcome, evaluate_capacity
from app.core.matrix.eligibility_rules import evaluate_eligibility
from app.core.matrix.matrix_schema import CAPACITY_COLUMNS, MatrixSchema

__all__ = ["build_matrix_core"]


def _ensure_iterable_records(frame: pd.DataFrame) -> Iterable[Mapping[str, object]]:
    records = cast(list[Mapping[str, object]], frame.to_dict(orient="records"))
    return records


def _trace_with_capacity(
    eligibility_trace: tuple[tuple[str, str], ...],
    capacity_status: str,
) -> list[tuple[str, str]]:
    trace = list(eligibility_trace)
    if trace and trace[-1][0] == "capacity_gate":
        trace[-1] = ("capacity_gate", capacity_status)
    else:
        trace.append(("capacity_gate", capacity_status))
    return trace


def _capacity_values(mentor: Mapping[str, object]) -> tuple[CapacityOutcome, dict[str, object]]:
    capacity_outcome = evaluate_capacity(mentor)
    capacity_fields = {
        "capacity_limit": mentor.get("capacity_limit", 0),
        "assigned_baseline": mentor.get("assigned_baseline", 0),
        "allocations_new": mentor.get("allocations_new", 0),
        "total_allocations": capacity_outcome.total_allocations,
        "remaining_capacity": capacity_outcome.remaining_capacity,
    }
    return capacity_outcome, capacity_fields


def build_matrix_core(
    mentors: pd.DataFrame,
    students: pd.DataFrame,
    *,
    schema: MatrixSchema | None = None,
) -> pd.DataFrame:
    """Build the MatrixCore DataFrame from canonical mentor and student frames."""

    schema = schema or MatrixSchema()
    if mentors.empty or students.empty:
        columns = (
            list(schema.join_keys)
            + list(CAPACITY_COLUMNS)
            + [
                "mentor_id",
                "student_id",
                "eligibility_ok",
                "capacity_ok",
                "blocking_codes",
                "soft_codes",
                "trace",
            ]
        )
        return pd.DataFrame(columns=columns)

    records: list[dict[str, object]] = []
    mentor_records = list(_ensure_iterable_records(mentors))
    student_records = list(_ensure_iterable_records(students))
    capacity_by_mentor: dict[int, tuple[CapacityOutcome, dict[str, object]]] = {}
    for mentor in mentor_records:
        mentor_id = cast(int, mentor.get("mentor_id", 0))
        capacity_by_mentor[mentor_id] = _capacity_values(mentor)

    for mentor in mentor_records:
        capacity_outcome, capacity_fields = capacity_by_mentor[mentor["mentor_id"]]
        for student in student_records:
            eligibility_outcome = evaluate_eligibility(mentor, student)
            if not eligibility_outcome.eligible:
                continue

            trace = _trace_with_capacity(
                eligibility_outcome.trace,
                "ok" if capacity_outcome.capacity_ok else "blocked",
            )

            record: dict[str, object] = {key: student[key] for key in schema.join_keys}
            record.update(
                {
                    "mentor_id": mentor["mentor_id"],
                    "student_id": student["student_id"],
                    "eligibility_ok": eligibility_outcome.eligible,
                    "capacity_ok": capacity_outcome.capacity_ok,
                    "blocking_codes": eligibility_outcome.blocking_codes
                    + capacity_outcome.blocking_codes,
                    "soft_codes": eligibility_outcome.soft_codes,
                    "trace": tuple(trace),
                }
            )
            record.update(capacity_fields)
            records.append(record)

    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df

    join_key_list = list(schema.join_keys)
    df[join_key_list] = df[join_key_list].apply(pd.to_numeric, errors="coerce").fillna(0).astype(int)
    df = df.sort_values(list(schema.ranking_fields), ascending=[False, True, True]).reset_index(
        drop=True
    )
    return df
