"""Join-key utilities shared across Core (Policy-First, no I/O)."""

from __future__ import annotations

from collections.abc import Mapping
from numbers import Number
from typing import Literal, TypedDict, cast

import pandas as pd

from app.core.common.columns import _GENDER_TOKEN_MAP, CANON_EN_TO_FA
from app.core.common.normalization import normalize_fa
from app.core.common.types import JOIN_KEY_GENDER
from app.core.counter import normalize_digits
from app.core.policy_loader import PolicyConfig

__all__ = [
    "JoinKeyCanonicalizationError",
    "JoinKeyMismatchDetail",
    "center_wildcard_value",
    "coerce_join_int",
    "canonicalize_join_key_value",
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


class JoinKeyCanonicalizationError(ValueError):
    """Raised when a join-key value cannot be canonicalized to ``int``."""

    def __init__(self, column: str, value: object) -> None:
        super().__init__("DATA_MISSING")
        self.column = column
        self.value = value


def coerce_join_int(value: object) -> int:
    """Coerce join-key payloads to int, raising on missing/invalid data."""

    if value is None:
        raise ValueError("DATA_MISSING")
    if isinstance(value, Number) and pd.isna(value):
        raise ValueError("DATA_MISSING")
    if isinstance(value, complex):
        raise ValueError("DATA_MISSING")
    if isinstance(value, str):
        digits = normalize_digits(value).strip()
        if not digits:
            raise ValueError("DATA_MISSING")
        return int(digits)
    return int(cast(int, value))


def canonicalize_join_key_value(column: str, value: object, *, policy: PolicyConfig) -> int:
    """Normalize a single join-key value to ``int`` using Policy mappings."""

    gender_column = CANON_EN_TO_FA.get("gender", JOIN_KEY_GENDER)
    normalized_column = normalize_join_key_name(column)
    is_gender = normalize_fa(normalized_column) == normalize_fa(gender_column)
    try:
        if is_gender:
            return _canonicalize_gender_value(value, policy)
        return coerce_join_int(value)
    except ValueError as exc:
        raise JoinKeyCanonicalizationError(column, value) from exc


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


def _canonicalize_gender_value(value: object, policy: PolicyConfig) -> int:
    normalized = normalize_fa(value)
    if not normalized:
        raise ValueError("DATA_MISSING")
    male_tokens = {token for token, code in _GENDER_TOKEN_MAP.items() if code == 1}
    female_tokens = {token for token, code in _GENDER_TOKEN_MAP.items() if code == 0}
    if normalized in male_tokens:
        return int(policy.gender_codes.male.value)
    if normalized in female_tokens:
        return int(policy.gender_codes.female.value)
    try:
        numeric = coerce_join_int(value)
    except ValueError as exc:
        raise ValueError("DATA_MISSING") from exc
    if numeric in {policy.gender_codes.male.value, policy.gender_codes.female.value}:
        return numeric
    raise ValueError("DATA_MISSING")


def validate_policy_join_keys(
    mentor_row: Mapping[str, object],
    join_map: Mapping[str, int],
    policy: PolicyConfig,
) -> tuple[bool, list[JoinKeyMismatchDetail]]:
    """Validate equality of all policy join keys between student and mentor."""

    mismatches: list[JoinKeyMismatchDetail] = []
    wildcard_center = center_wildcard_value(policy)
    finance_variants = set(policy.finance_variants)
    for column in policy.join_keys:
        normalized = normalize_join_key_name(column)
        student_value = join_map.get(normalized)
        mentor_raw = mentor_row.get(column)
        mentor_value: int | None
        if column == policy.stage_column("gender"):
            try:
                mentor_value = canonicalize_join_key_value(column, mentor_raw, policy=policy)
            except JoinKeyCanonicalizationError:
                mentor_value = None
        else:
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
        student_int = int(student_value)
        if column == policy.stage_column("center") and matches_center_with_wildcard(
            student_int, mentor_value, wildcard_center
        ):
            continue
        if (
            column == policy.stage_column("finance")
            and mentor_value in finance_variants
            and student_int in finance_variants
        ):
            continue
        if column == policy.columns.school_code and matches_school_with_wildcard(
            student_int, mentor_value, policy.school_code_empty_as_zero
        ):
            continue
        if mentor_value != student_int:
            mismatches.append(
                {
                    "column": column,
                    "student_value": student_int,
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
