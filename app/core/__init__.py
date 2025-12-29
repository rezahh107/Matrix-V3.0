"""Public Core API surface for allocation operations."""

from __future__ import annotations

from app.core.allocate import enforce_allocation_output_contracts
from app.core.allocate_students import (
    AllocationBatchResult,
    AllocationResult,
    allocate_batch,
    allocate_student,
    build_selection_reason_rows,
)

__all__ = [
    "AllocationBatchResult",
    "AllocationResult",
    "allocate_batch",
    "allocate_student",
    "build_selection_reason_rows",
    "enforce_allocation_output_contracts",
]
