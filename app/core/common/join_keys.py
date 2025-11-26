"""Join-key utilities shared across Core (Policy-First, no I/O)."""

from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Literal, TypedDict, cast

import pandas as pd

from app.core.policy_loader import PolicyConfig

__all__ = [
    "JoinKeyMismatchDetail",
    "center_wildcard_value",
    "coerce_join_int",
    "matches_center_with_wildcard",
    "matches_school_with_wildcard",
    "normalize_join_key_name",
    "validate_policy_join_keys",
    "validate_selected_mentor_join_keys",
]


class JoinKeyMismatchDetail(TypedDict):
    """Structured mismatch entry for join-key validation."""

    column: str
    student_value: int | None
    mentor_value: object | None
    mismatch_type: Literal["unequal", "missing", "wildcard_mismatch"]


def coerce_join_int(value: object) -> int:
    """Coerce join-key payloads to int, raising on missing/invalid data."""

    if value is None:
        raise ValueError("DATA_MISSING")
    if isinstance(value, Number) and pd.isna(value):
        raise ValueError("DATA_MISSING")
    if isinstance(value, complex):
        raise ValueError("DATA_MISSING")
    return int(cast(int, value))


def normalize_join_key_name(column: str) -> str:
    """Normalize join-key names to the underscore form used in join_map."""

    return column.replace(" ", "_")


def center_wildcard_value(policy: PolicyConfig) -> int | None:
    """Fetch center wildcard value from Policy if present."""

    wildcard = policy.center_map.get("*")
    if wildcard is None:
        return None
    try:
        return int(wildcard)
    except (TypeError, ValueError):
        return None


def matches_center_with_wildcard(
    student_center: int, mentor_center: int, wildcard_center: int | None
) -> bool:
    """Compare center with wildcard support."""

    if wildcard_center is not None and student_center == wildcard_center:
        return True
    return mentor_center == student_center


def matches_school_with_wildcard(
    student_school: int, mentor_school: int, empty_as_zero: bool
) -> bool:
    """Compare school code with optional zero-as-wildcard policy."""

    if empty_as_zero and (student_school == 0 or mentor_school == 0):
        return True
    return mentor_school == student_school


def _coerce_optional_int(value: object) -> int | None:
    try:
        return coerce_join_int(value)
    except Exception:
        return None


def validate_policy_join_keys(
    mentor_row: Mapping[str, object],
    join_map: Mapping[str, int],
    policy: PolicyConfig,
) -> tuple[bool, list[JoinKeyMismatchDetail]]:
    """Validate equality of all policy join keys between student and mentor."""

    mismatches: list[JoinKeyMismatchDetail] = []
    wildcard_center = center_wildcard_value(policy)
    for column in policy.join_keys:
        normalized = normalize_join_key_name(column)
        student_value = join_map.get(normalized)
        mentor_raw = mentor_row.get(column)
        mentor_value = _coerce_optional_int(mentor_raw)
        if student_value is None:
            mismatches.append(
                {
                    "column": column,
                    "student_value": None,
                    "mentor_value": mentor_value,
                    "mismatch_type": "missing",
                }
            )
            continue
        if mentor_value is None:
            mismatches.append(
                {
                    "column": column,
                    "student_value": int(student_value),
                    "mentor_value": mentor_raw,
                    "mismatch_type": "missing",
                }
            )
            continue
        if column == policy.stage_column("center") and matches_center_with_wildcard(
            int(student_value), mentor_value, wildcard_center
        ):
            continue
        if column == policy.columns.school_code and matches_school_with_wildcard(
            int(student_value), mentor_value, policy.school_code_empty_as_zero
        ):
            continue
        if mentor_value != int(student_value):
            mismatches.append(
                {
                    "column": column,
                    "student_value": int(student_value),
                    "mentor_value": mentor_value,
                    "mismatch_type": "unequal",
                }
            )
    return (len(mismatches) == 0), mismatches


def validate_selected_mentor_join_keys(
    selected_row: Mapping[str, object],
    *,
    student_join_map: Mapping[str, int],
    policy: PolicyConfig,
) -> tuple[bool, list[JoinKeyMismatchDetail]]:
    """Pre-consume validation guard for selected mentor join keys."""

    return validate_policy_join_keys(selected_row, student_join_map, policy)
