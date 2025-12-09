from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.core.matrix.matrix_schema import CAPACITY_COLUMNS

__all__ = ["CapacityOutcome", "evaluate_capacity"]


@dataclass(frozen=True)
class CapacityOutcome:
    """Result of applying capacity gates to a mentor row."""

    capacity_ok: bool
    remaining_capacity: int
    total_allocations: int
    blocking_codes: tuple[str, ...]


def _safe_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except Exception:
        return 0


def evaluate_capacity(mentor_row: Mapping[str, object]) -> CapacityOutcome:
    """Compute capacity outcome using LAW/CAPACITY-FIELDS-01 semantics."""

    blocking: list[str] = []

    capacity_limit = _safe_int(mentor_row.get("capacity_limit", 0))
    assigned_baseline = _safe_int(mentor_row.get("assigned_baseline", 0))
    allocations_new = _safe_int(mentor_row.get("allocations_new", 0))
    capacity_special = _safe_int(mentor_row.get("capacity_special", 0))
    is_frozen = bool(mentor_row.get("capacity_frozen", False))

    if capacity_limit <= 0:
        blocking.append("capacity_limit_missing")

    effective_limit = capacity_limit + max(capacity_special, 0)
    total_allocations = assigned_baseline + allocations_new
    remaining_capacity = effective_limit - total_allocations

    if is_frozen:
        blocking.append("capacity_frozen")
    if remaining_capacity <= 0:
        blocking.append("capacity_exhausted")

    return CapacityOutcome(
        capacity_ok=not blocking,
        remaining_capacity=remaining_capacity,
        total_allocations=total_allocations,
        blocking_codes=tuple(blocking),
    )


CAPACITY_FIELDS = CAPACITY_COLUMNS
