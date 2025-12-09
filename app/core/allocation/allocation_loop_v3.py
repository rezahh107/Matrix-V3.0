from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

from app.core.allocation.ranking import (
    CapacityStateEntry,
    apply_allocation,
    apply_state_to_candidates,
    build_capacity_state,
    filter_rankable_candidates,
    rank_candidates,
)
from app.core.allocation.trace_steps import build_trace_frame, normalize_trace_steps
from app.core.matrix.matrix_schema import MatrixSchema

__all__ = ["AllocationDecision", "run_allocation_loop_v3"]


@dataclass(frozen=True)
class AllocationDecision:
    """Allocation decision for a single student."""

    student_id: int
    mentor_id: int | None
    trace: tuple[tuple[str, str], ...]


def _student_order(matrix_core: pd.DataFrame) -> list[int]:
    students = pd.unique(matrix_core.get("student_id", pd.Series(dtype=int)))
    return sorted(int(value) for value in students)


def _candidate_rows(matrix_core: pd.DataFrame, student_id: int) -> pd.DataFrame:
    mask = matrix_core["student_id"] == student_id
    return matrix_core[mask].reset_index(drop=True)


def _update_trace_capacity(
    trace: Iterable[tuple[str, str]], *, capacity_status: str, schema: MatrixSchema
) -> tuple[tuple[str, str], ...]:
    mapping = {stage: value for stage, value in trace}
    mapping["capacity_gate"] = capacity_status
    normalized = normalize_trace_steps(mapping.items(), schema=schema)
    return normalized


def _unassigned_trace(
    candidates: pd.DataFrame, *, schema: MatrixSchema
) -> tuple[tuple[str, str], ...]:
    base_trace = candidates.iloc[0]["trace"] if not candidates.empty else ()
    return _update_trace_capacity(base_trace or (), capacity_status="blocked", schema=schema)


def _decide_for_student(
    matrix_core: pd.DataFrame,
    state: dict[int, CapacityStateEntry],
    *,
    schema: MatrixSchema,
) -> AllocationDecision:
    student_id = int(matrix_core.iloc[0]["student_id"])
    candidates = apply_state_to_candidates(matrix_core, state)
    candidates = filter_rankable_candidates(candidates)
    if candidates.empty:
        trace = _unassigned_trace(matrix_core, schema=schema)
        return AllocationDecision(student_id=student_id, mentor_id=None, trace=trace)

    ranked = rank_candidates(candidates, schema=schema)
    chosen = ranked.iloc[0]
    mentor_id = int(chosen["mentor_id"])
    apply_allocation(state, mentor_id)

    trace = _update_trace_capacity(chosen.get("trace", ()), capacity_status="ok", schema=schema)
    return AllocationDecision(student_id=student_id, mentor_id=mentor_id, trace=trace)


def run_allocation_loop_v3(
    matrix_core: pd.DataFrame, *, schema: MatrixSchema | None = None
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deterministic allocation loop over MatrixCore rows.

    Returns a tuple of (allocations_df, trace_df).
    """

    schema = schema or MatrixSchema()
    if matrix_core.empty:
        empty_allocation = pd.DataFrame(columns=["student_id", "mentor_id"])
        empty_trace = build_trace_frame([], schema=schema)
        return empty_allocation, empty_trace

    state = build_capacity_state(matrix_core, schema=schema)

    decisions: list[AllocationDecision] = []
    for student_id in _student_order(matrix_core):
        student_rows = _candidate_rows(matrix_core, student_id)
        decision = _decide_for_student(student_rows, state, schema=schema)
        decisions.append(decision)

    allocation_records = [
        {"student_id": decision.student_id, "mentor_id": decision.mentor_id}
        for decision in decisions
    ]
    trace_records = [
        {
            "student_id": decision.student_id,
            "mentor_id": decision.mentor_id,
            "trace": decision.trace,
        }
        for decision in decisions
    ]

    allocations_df = pd.DataFrame.from_records(allocation_records, columns=["student_id", "mentor_id"])
    trace_df = build_trace_frame(trace_records, schema=schema)
    return allocations_df, trace_df
