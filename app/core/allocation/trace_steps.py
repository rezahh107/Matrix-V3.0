from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import cast

import pandas as pd

from app.core.matrix.matrix_schema import MatrixSchema

__all__ = [
    "normalize_trace_steps",
    "build_trace_frame",
]


def _trace_mapping(trace: Iterable[tuple[str, str]] | None) -> dict[str, str]:
    if trace is None:
        return {}
    return {stage: str(value) for stage, value in trace}


def normalize_trace_steps(
    trace: Iterable[tuple[str, str]] | None, *, schema: MatrixSchema | None = None
) -> tuple[tuple[str, str], ...]:
    """Return a normalized 8-step trace tuple aligned with LAW/TRACE-8STEP-01."""

    schema = schema or MatrixSchema()
    mapping = _trace_mapping(trace)
    normalized: list[tuple[str, str]] = []
    for step in schema.trace_steps:
        normalized.append((step, mapping.get(step, "")))
    return tuple(normalized)


def build_trace_frame(
    rows: Iterable[Mapping[str, object]], *, schema: MatrixSchema | None = None
) -> pd.DataFrame:
    """Create a DataFrame with explicit columns for the 8 trace steps."""

    schema = schema or MatrixSchema()
    records: list[dict[str, object]] = []
    for row in rows:
        trace_value = cast(Iterable[tuple[str, str]] | None, row.get("trace"))
        trace = normalize_trace_steps(trace_value, schema=schema)
        record = {
            "student_id": row.get("student_id"),
            "mentor_id": row.get("mentor_id"),
        }
        for stage, value in trace:
            record[stage] = value
        records.append(record)
    columns = ["student_id", "mentor_id", *schema.trace_steps]
    return pd.DataFrame.from_records(records, columns=columns)
