"""Join-key utilities shared across Core (Policy-First, no I/O)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from numbers import Number
from typing import Literal, TypedDict, cast

import pandas as pd

from app.core.common.columns import _GENDER_TOKEN_MAP, CANON_EN_TO_FA
from app.core.common.normalization import normalize_fa
from app.core.common.types import CANONICAL_JOIN_KEYS, JOIN_KEY_GENDER, JoinKeyName
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
    "finance_variants_from_cell",
    "resolve_finance_variants",
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
        super().__init__(f"Cannot canonicalize join key '{column}' from value {value!r}")
        self.column = column
        self.value = value


def coerce_join_int(value: object) -> int:
    """Coerce join-key payloads to int, raising on missing/invalid data."""

    if value is None:
        raise ValueError("DATA_MISSING")
    if not isinstance(value, str):
        try:
            if pd.isna(value):
                raise ValueError("DATA_MISSING")
        except TypeError:
            pass
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


def _canonical_join_key_name(column: str) -> JoinKeyName:
    normalized = normalize_fa(column)
    resolved = _JOIN_KEY_LOOKUP.get(normalized)
    if resolved is None:
        raise ValueError(f"Unknown join key: {column}")
    return resolved


def _is_gender_key(column: JoinKeyName, policy: PolicyConfig) -> bool:
    gender_column = CANON_EN_TO_FA.get("gender", JOIN_KEY_GENDER)
    return normalize_fa(column) == normalize_fa(gender_column) or normalize_fa(
        policy.stage_column("gender")
    ) == normalize_fa(column)


def _is_center_key(column: JoinKeyName, policy: PolicyConfig) -> bool:
    return normalize_fa(column) == normalize_fa(policy.stage_column("center"))


def _is_school_key(column: JoinKeyName, policy: PolicyConfig) -> bool:
    return normalize_fa(column) == normalize_fa(policy.columns.school_code)


def _is_missing_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, Number) and pd.isna(value):
        return True
    if isinstance(value, str):
        return not normalize_digits(value).strip()
    return False


def _iterable_values(raw: object) -> Iterable[object]:
    if isinstance(raw, Mapping):
        return raw.values()
    if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
        return raw
    return (raw,)


def _canonicalize_numeric_value(value: object, *, allow_zero_from_empty: bool) -> int:
    if _is_missing_value(value):
        if allow_zero_from_empty:
            return 0
        raise ValueError("DATA_MISSING")
    last_error: ValueError | None = None
    for candidate in _iterable_values(value):
        try:
            return coerce_join_int(candidate)
        except ValueError as exc:  # pragma: no cover - loop handles next candidate
            last_error = exc
            continue
    if allow_zero_from_empty:
        return 0
    raise last_error if last_error is not None else ValueError("DATA_MISSING")


def canonicalize_join_key_value(column: str, value: object, *, policy: PolicyConfig) -> int:
    """Normalize a single join-key value to ``int`` using Policy mappings."""

    try:
        join_key = _canonical_join_key_name(column)
        if _is_gender_key(join_key, policy):
            return _canonicalize_gender_value(value, policy)
        if _is_center_key(join_key, policy):
            return _canonicalize_center_value(value, policy)
        if _is_school_key(join_key, policy):
            return _canonicalize_school_value(value, policy)
        return _canonicalize_numeric_value(value, allow_zero_from_empty=False)
    except ValueError as exc:
        raise JoinKeyCanonicalizationError(column, value) from exc


def _canonicalize_center_value(value: object, policy: PolicyConfig) -> int:
    center_lookup = {normalize_fa(str(key)): int(val) for key, val in policy.center_map.items()}
    if isinstance(value, str):
        if not value.strip():
            raise ValueError("DATA_MISSING")
        normalized = normalize_fa(value)
        normalized_star = normalize_fa("*")
        mapped = center_lookup.get(normalized)
        if mapped is not None and normalized:
            return mapped
        if normalized == normalized_star:
            mapped_star = center_lookup.get(normalized_star)
            if mapped_star is not None:
                return mapped_star
    return _canonicalize_numeric_value(value, allow_zero_from_empty=False)


def _canonicalize_school_value(value: object, policy: PolicyConfig) -> int:
    return _canonicalize_numeric_value(
        value, allow_zero_from_empty=policy.school_code_empty_as_zero
    )


def normalize_join_key_name(column: str) -> str:
    """Normalize join-key names to the underscore form used in join_map."""

    return column.replace(" ", "_")


_JOIN_KEY_LOOKUP: dict[str, JoinKeyName] = {
    normalize_fa(name): cast(JoinKeyName, name) for name in CANONICAL_JOIN_KEYS
}
for en_key in (
    "group_code",
    "gender",
    "graduation_status",
    "center",
    "finance",
    "school_code",
):
    fa_value = CANON_EN_TO_FA.get(en_key)
    if fa_value is None:
        continue
    normalized = normalize_fa(fa_value)
    canonical_name = cast(JoinKeyName, normalize_join_key_name(fa_value))
    if normalized not in _JOIN_KEY_LOOKUP:
        _JOIN_KEY_LOOKUP[normalized] = canonical_name
    _JOIN_KEY_LOOKUP.setdefault(normalize_fa(en_key), canonical_name)


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
    """Compare centers using mentor-side-only wildcard semantics."""

    wildcard_values: set[int] = {int(wildcard_center)} if wildcard_center is not None else {0}
    if mentor_center in wildcard_values:
        return True
    return mentor_center == student_center


def matches_school_with_wildcard(
    student_school: int, mentor_school: int, empty_as_zero: bool
) -> bool:
    """Compare school code with optional zero-as-wildcard policy."""

    if empty_as_zero and (student_school == 0 or mentor_school == 0):
        return True
    return mentor_school == student_school


def finance_variants_from_cell(value: object, policy: PolicyConfig) -> frozenset[int]:
    """استخراج مجموعهٔ کدهای مالی منتور برای مقایسهٔ چندمقداری."""

    if isinstance(value, Mapping):
        variants: set[int] = set()
        for item in value.values():
            try:
                variants.update(resolve_finance_variants(coerce_join_int(item), policy))
            except (ValueError, TypeError):
                continue
        return frozenset(variants)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        collected: set[int] = set()
        for item in value:
            try:
                collected.update(resolve_finance_variants(coerce_join_int(item), policy))
            except (ValueError, TypeError):
                continue
        return frozenset(collected)
    try:
        coerced = coerce_join_int(value)
    except (ValueError, TypeError):
        return frozenset()
    return resolve_finance_variants(coerced, policy)


def _extract_finance_variants(value: object, policy: PolicyConfig) -> frozenset[int]:
    """Compatibility wrapper for legacy callers."""

    return finance_variants_from_cell(value, policy)


def resolve_finance_variants(student_finance: int, policy: PolicyConfig) -> frozenset[int]:
    """استخراج مجموعهٔ variantهای مالی بر اساس Policy.

    ورودی «student_finance» یک کد عددی است. اگر این کد در ``finance_variants``
    تعریف‌شدهٔ Policy حضور داشته باشد، تمام variantها به‌صورت یک ``frozenset``
    بازگردانده می‌شوند تا فیلتر مالی از روی برابری چند مقداری (`isin`) اجرا شود.
    در غیر این صورت، همان مقدار دانش‌آموز به‌تنهایی بازگردانده می‌شود تا رفتار
    قبلی حفظ گردد.
    """

    def _normalize_iterable(raw: object) -> frozenset[int]:
        if isinstance(raw, Mapping):
            return frozenset(coerce_join_int(item) for item in raw.values())
        if isinstance(raw, Sequence) and not isinstance(raw, (str, bytes)):
            return frozenset(coerce_join_int(item) for item in raw)
        return frozenset({coerce_join_int(raw)})

    finance_value = coerce_join_int(student_finance)
    finance_variants = policy.finance_variants
    if isinstance(finance_variants, Mapping):
        for canonical_value, variants in finance_variants.items():
            variant_values = _normalize_iterable(variants)
            bucket: set[int] = {coerce_join_int(canonical_value), *variant_values}
            if finance_value in bucket:
                return frozenset(bucket)
        return frozenset({finance_value})

    has_nested_clusters = any(
        isinstance(entry, Sequence) and not isinstance(entry, (str, bytes))
        for entry in finance_variants
    )
    if has_nested_clusters:
        for cluster in finance_variants:
            if isinstance(cluster, Sequence) and not isinstance(cluster, (str, bytes)):
                bucket_set = _normalize_iterable(cluster)
                if finance_value in bucket_set:
                    return bucket_set
        return frozenset({finance_value})

    flat_variants = _normalize_iterable(finance_variants)
    if finance_value in flat_variants:
        return flat_variants
    return frozenset({finance_value})


def _canonicalize_optional_value(column: str, value: object, policy: PolicyConfig) -> int | None:
    try:
        return canonicalize_join_key_value(column, value, policy=policy)
    except JoinKeyCanonicalizationError:
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
    for column in policy.join_keys:
        normalized = normalize_join_key_name(column)
        student_value = join_map.get(normalized)
        mentor_raw = mentor_row.get(column)
        mentor_value = _canonicalize_optional_value(column, mentor_raw, policy)
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
        student_int = int(student_value)
        if column == policy.stage_column("finance"):
            allowed_student_variants = resolve_finance_variants(student_int, policy)
            mentor_variants = finance_variants_from_cell(mentor_raw, policy)
            if mentor_variants and allowed_student_variants.intersection(mentor_variants):
                continue
            if mentor_value is None:
                mismatches.append(
                    {
                        "column": column,
                        "student_value": student_int,
                        "mentor_value": mentor_raw,
                        "mismatch_type": "missing",
                    }
                )
                continue
            mismatches.append(
                {
                    "column": column,
                    "student_value": student_int,
                    "mentor_value": mentor_raw,
                    "mismatch_type": "unequal",
                }
            )
            continue
        if mentor_value is None:
            mismatches.append(
                {
                    "column": column,
                    "student_value": student_int,
                    "mentor_value": mentor_raw,
                    "mismatch_type": "missing",
                }
            )
            continue
        if column == policy.stage_column("center"):
            if matches_center_with_wildcard(student_int, mentor_value, wildcard_center):
                continue
            mismatches.append(
                {
                    "column": column,
                    "student_value": student_int,
                    "mentor_value": mentor_value,
                    "mismatch_type": "unequal",
                }
            )
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
