from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.core.matrix.matrix_schema import JOIN_KEY_COLUMNS

TRACE_KEY_MAP: Mapping[str, str] = {
    "group_code": "group",
    "gender_code": "gender",
    "grad_status_code": "graduation_status",
    "center_code": "center",
    "finance_code": "finance",
    "school_code": "school",
}

__all__ = ["EligibilityOutcome", "evaluate_eligibility"]


@dataclass(frozen=True)
class EligibilityOutcome:
    """Result of eligibility evaluation for a mentor/student pair."""

    eligible: bool
    blocking_codes: tuple[str, ...]
    soft_codes: tuple[str, ...]
    trace: tuple[tuple[str, str], ...]


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except Exception:
        return 0


def _matches_with_wildcard(mentor_value: int, student_value: int, *, allow_zero: bool) -> bool:
    if mentor_value == student_value:
        return True
    return bool(allow_zero and mentor_value == 0)


def evaluate_eligibility(
    mentor_row: Mapping[str, object],
    student_row: Mapping[str, object],
    *,
    join_keys: Sequence[str] = JOIN_KEY_COLUMNS,
) -> EligibilityOutcome:
    """Apply LAW/TECH eligibility constraints.

    The function is pure and deterministic: mappings in, outcome out. The
    canonical six join keys are checked in order with explicit trace steps.
    """

    blocking: list[str] = []
    soft: list[str] = []
    trace_steps: list[tuple[str, str]] = [("type", "matrix_core")]

    join_key_map = {key: TRACE_KEY_MAP.get(key, key) for key in join_keys}

    for key in join_keys:
        mentor_value = _int_value(mentor_row.get(key, 0))
        student_value = _int_value(student_row.get(key, 0))
        step_label = join_key_map.get(key, key)
        if key in {"center_code", "school_code"}:
            matches = _matches_with_wildcard(mentor_value, student_value, allow_zero=True)
        else:
            matches = mentor_value == student_value
        if not matches:
            reason = f"{key}_mismatch"
            blocking.append(reason)
            trace_steps.append((step_label, "blocked"))
            break
        trace_steps.append((step_label, "ok"))

    eligible = not blocking
    if not eligible:
        return EligibilityOutcome(
            eligible=False,
            blocking_codes=tuple(blocking),
            soft_codes=tuple(soft),
            trace=tuple(trace_steps),
        )

    trace_steps.append(("capacity_gate", "pending"))
    return EligibilityOutcome(
        eligible=True,
        blocking_codes=tuple(blocking),
        soft_codes=tuple(soft),
        trace=tuple(trace_steps),
    )
