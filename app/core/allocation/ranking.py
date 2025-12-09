from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass

import pandas as pd

from app.core.common.types import natural_key
from app.core.matrix.matrix_schema import MatrixSchema

__all__ = [
    "CapacityStateEntry",
    "build_capacity_state",
    "apply_state_to_candidates",
    "filter_rankable_candidates",
    "rank_candidates",
    "apply_allocation",
]


@dataclass
class CapacityStateEntry:
    """Mutable capacity snapshot for a mentor during AllocationLoopV3.

    The state mirrors LAW/CAPACITY-FIELDS-01 without altering semantics:
    - ``remaining`` tracks remaining_capacity.
    - ``allocations_new`` counts new allocations in this run.
    - ``total_allocations`` mirrors assigned_baseline + allocations_new.
    """

    remaining: int
    allocations_new: int
    total_allocations: int


def _safe_int(value: object) -> int:
    if isinstance(value, int):
        return max(value, 0)
    try:
        numeric = int(float(str(value)))
    except (TypeError, ValueError):
        return 0
    return max(numeric, 0)


def build_capacity_state(matrix_core: pd.DataFrame, *, schema: MatrixSchema | None = None) -> dict[int, CapacityStateEntry]:
    """Initialize mutable capacity state from MatrixCore rows."""

    schema = schema or MatrixSchema()
    required = {"mentor_id", *schema.capacity_fields}
    missing = required - set(matrix_core.columns)
    if missing:
        raise KeyError(f"matrix_core missing required capacity fields: {sorted(missing)}")

    state: dict[int, CapacityStateEntry] = {}
    for mentor_id, group in matrix_core.groupby("mentor_id", sort=False):
        remaining = _safe_int(group.iloc[0]["remaining_capacity"])
        allocations_new = _safe_int(group.iloc[0]["allocations_new"])
        total_allocations = _safe_int(group.iloc[0]["total_allocations"])
        state[int(mentor_id)] = CapacityStateEntry(
            remaining=remaining,
            allocations_new=allocations_new,
            total_allocations=total_allocations,
        )
    return state


def apply_state_to_candidates(
    candidates: pd.DataFrame, state: Mapping[int, CapacityStateEntry]
) -> pd.DataFrame:
    """Return a copy of candidates with capacity fields refreshed from state."""

    if candidates.empty:
        return candidates.copy()
    working = candidates.copy()
    working["mentor_id"] = working["mentor_id"].astype(int)

    def _lookup_field(mentor_id: int, attr: str) -> int:
        entry = state.get(mentor_id)
        if entry is None:
            return 0
        return getattr(entry, attr)

    working["remaining_capacity"] = working["mentor_id"].map(
        lambda mentor_id: _lookup_field(mentor_id, "remaining")
    )
    working["allocations_new"] = working["mentor_id"].map(
        lambda mentor_id: _lookup_field(mentor_id, "allocations_new")
    )
    working["total_allocations"] = working["mentor_id"].map(
        lambda mentor_id: _lookup_field(mentor_id, "total_allocations")
    )
    return working


def filter_rankable_candidates(candidates: pd.DataFrame) -> pd.DataFrame:
    """Drop mentors that fail capacity gates or have no remaining capacity."""

    if candidates.empty:
        return candidates.copy()
    working = candidates.copy()
    if "capacity_ok" in working.columns:
        working = working[working["capacity_ok"].astype(bool)]
    if "remaining_capacity" in working.columns:
        working = working[working["remaining_capacity"] > 0]
    return working.reset_index(drop=True)


def rank_candidates(candidates: pd.DataFrame, *, schema: MatrixSchema | None = None) -> pd.DataFrame:
    """Sort candidates deterministically using LAW/RANKING-ORDER-01."""

    schema = schema or MatrixSchema()
    if candidates.empty:
        return candidates.copy()

    missing = set(schema.ranking_fields) - set(candidates.columns)
    if missing:
        raise KeyError(f"Missing ranking columns: {sorted(missing)}")

    working = candidates.copy()
    working["mentor_sort_key"] = working["mentor_id"].map(natural_key)
    sort_by: list[str] = [
        "remaining_capacity",
        "allocations_new",
        "mentor_sort_key",
    ]
    ascending = [False, True, True]
    working = working.sort_values(by=sort_by, ascending=ascending, kind="mergesort")
    return working.reset_index(drop=True)


def apply_allocation(
    state: MutableMapping[int, CapacityStateEntry], mentor_id: int
) -> None:
    """Consume one unit of capacity for mentor_id, raising on underflow."""

    if mentor_id not in state:
        raise KeyError(f"Mentor {mentor_id} missing from state")
    entry = state[mentor_id]
    if entry.remaining <= 0:
        raise ValueError("CAPACITY_UNDERFLOW")
    entry.remaining -= 1
    entry.allocations_new += 1
    entry.total_allocations += 1
