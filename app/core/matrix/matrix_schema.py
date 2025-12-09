from __future__ import annotations

from dataclasses import dataclass
from typing import Final

__all__ = ["JOIN_KEY_COLUMNS", "CAPACITY_COLUMNS", "TRACE_STEPS", "MatrixSchema"]

JOIN_KEY_COLUMNS: Final[tuple[str, ...]] = (
    "group_code",
    "gender_code",
    "grad_status_code",
    "center_code",
    "finance_code",
    "school_code",
)

CAPACITY_COLUMNS: Final[tuple[str, ...]] = (
    "capacity_limit",
    "assigned_baseline",
    "allocations_new",
    "total_allocations",
    "remaining_capacity",
)

TRACE_STEPS: Final[tuple[str, ...]] = (
    "type",
    "group",
    "gender",
    "graduation_status",
    "center",
    "finance",
    "school",
    "capacity_gate",
)


@dataclass(frozen=True)
class MatrixSchema:
    """MatrixCore schema definition.

    This schema keeps the canonical join keys, capacity fields, QA flags, and
    trace steps aligned with LAW/Technical SSoT without introducing new rules.

    The ``ranking_fields`` tuple encodes the invariant 3-key ordering
    (remaining_capacity ↓, allocations_new ↑, mentor_id ↑) from LAW/RANK-CORE-01
    and MUST stay in this order.
    """

    join_keys: tuple[str, ...] = JOIN_KEY_COLUMNS
    capacity_fields: tuple[str, ...] = CAPACITY_COLUMNS
    qa_fields: tuple[str, ...] = (
        "eligibility_ok",
        "capacity_ok",
        "blocking_codes",
        "soft_codes",
    )
    ranking_fields: tuple[str, ...] = (
        "remaining_capacity",
        "allocations_new",
        "mentor_id",
    )
    trace_steps: tuple[str, ...] = TRACE_STEPS
