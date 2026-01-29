"""Join-key utilities shared across Core (Policy-First, no I/O)."""

from __future__ import annotations

import re
from collections.abc import Callable, Hashable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from numbers import Number
from typing import Literal, TypedDict, cast

import numpy as np
import pandas as pd

from app.core.common.columns import _GENDER_TOKEN_MAP, CANON_EN_TO_FA, ensure_series
from app.core.common.domain import VALID_GROUP_CODES
from app.core.common.isin_guard import isin_mask
from app.core.common.normalization import normalize_fa, to_numlike_str
from app.core.common.types import (
    CANONICAL_JOIN_KEYS,
    JOIN_KEY_GENDER,
    JoinKeyEntityType,
    JoinKeyName,
    JoinKeyValidationIssue,
    JoinKeyValidationResult,
)
from app.core.counter import normalize_digits, strip_hidden_chars
from app.core.policy_loader import PolicyConfig

__all__ = [
    "JoinKeyCanonicalizationError",
    "JoinKeyMismatchDetail",
    "StudentSchoolCode",
    "center_wildcard_value",
    "coerce_school_candidate",
    "finance_mask_series",
    "coerce_join_int",
    "canonicalize_join_key_value",
    "matches_center_with_wildcard",
    "matches_school_with_wildcard",
    "normalize_join_key_name",
    "parse_group_codes",
    "finance_variants_from_cell",
    "resolve_finance_variants",
    "sanitize_school_series",
    "school_mask_series",
    "validate_policy_join_keys",
    "validate_selected_mentor_join_keys",
    "validate_and_canonicalize_join_keys",
    "assert_canonical_join_keys",
]


class JoinKeyMismatchDetail(TypedDict):
    """Structured mismatch entry for join-key validation."""

    column: str
    student_value: int | None
    mentor_value: object | None
    mismatch_type: Literal["unequal", "missing", "wildcard_mismatch"]


class JoinKeyCanonicalizationError(ValueError):
    """Raised when a join-key value cannot be canonicalized to ``int``."""

    def __init__(
        self,
        column: str,
        value: object,
        *,
        index: Hashable | None = None,
        error_code: str = "DATA_INVALID",
    ) -> None:
        suffix = "" if index is None else f" at index {index!r}"
        super().__init__(f"Cannot canonicalize join key '{column}'{suffix} from value {value!r}")
        self.column = column
        self.value = value
        self.index = index
        self.error_code = error_code


_SCHOOL_CODE_TRANSLATION = str.maketrans(
    {
        "-": " ",
        "−": " ",  # minus sign
        "‑": " ",  # non-breaking hyphen
        "–": " ",  # en dash
        "—": " ",  # em dash
        "―": " ",  # horizontal bar
        "﹘": " ",  # small em dash
        "﹣": " ",  # small hyphen-minus
        "／": " ",  # full-width slash
        "/": " ",
        "\\": " ",
        "⁄": " ",
        "ـ": "",  # kashida
    }
)


@dataclass(frozen=True)
class StudentSchoolCode:
    """نمایش نرمال‌شدهٔ «کد مدرسه» همراه با وضعیت کمبود و wildcard."""

    value: int | None
    missing: bool
    wildcard: bool


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
        digits = strip_hidden_chars(normalize_digits(value))
        digits = re.sub(r"\s+", "", digits)
        if not digits:
            raise ValueError("DATA_MISSING")
        return int(digits)
    return int(cast(int, value))


def _canonicalize_join_key_value_safe(
    column: str, value: object, *, policy: PolicyConfig
) -> tuple[int | None, str | None]:
    try:
        coerced = canonicalize_join_key_value(column, value, policy=policy)
        return coerced, None
    except JoinKeyCanonicalizationError as exc:
        return None, exc.error_code


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


def _is_group_key(column: JoinKeyName, policy: PolicyConfig) -> bool:
    return normalize_fa(column) == normalize_fa(policy.stage_column("group"))


def _is_missing_value(value: object) -> bool:
    if value is None:
        return True
    try:
        if bool(pd.isna(value)):
            return True
    except (TypeError, ValueError):
        pass
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
            coerced = coerce_join_int(candidate)
            if coerced < 0:
                raise ValueError("DATA_MISSING")
            return coerced
        except ValueError as exc:  # pragma: no cover - loop handles next candidate
            last_error = exc
            continue
    if last_error is not None:
        raise last_error
    if allow_zero_from_empty:
        return 0
    raise ValueError("DATA_MISSING")


def coerce_school_candidate(candidate: object) -> tuple[int | None, bool]:
    """تبدیل مقدار خام کد مدرسه به int یا علامت‌گذاری کمبود."""

    if candidate is None or candidate is pd.NA:
        return None, True
    if isinstance(candidate, (int, float, np.integer, np.floating)) and not isinstance(
        candidate, bool
    ):
        if pd.isna(candidate):
            return None, True
        return int(float(candidate)), False
    if isinstance(candidate, (bytes, bytearray)):
        try:
            candidate = candidate.decode("utf-8", "ignore")
        except UnicodeDecodeError:
            return None, True
    if isinstance(candidate, str):
        candidate = candidate.translate(_SCHOOL_CODE_TRANSLATION)
    text = to_numlike_str(candidate).strip()
    if not text:
        return None, True
    try:
        return int(float(text)), False
    except ValueError:
        return None, True


def sanitize_school_series(series: pd.Series) -> pd.Series:
    """بازگرداندن Series از مقادیر نرمال‌شدهٔ کد مدرسه بدون mutate ورودی."""

    def _clean(value: object) -> int | None:
        coerced, missing = coerce_school_candidate(value)
        return None if missing else coerced

    # Using .map is more idiomatic and can be more performant than iterating.
    cleaned_series = series.map(_clean)
    numeric = pd.to_numeric(cleaned_series, errors="coerce")
    return numeric.astype("Int64")


def school_mask_series(
    mentor_series: pd.Series,
    *,
    student_school: int,
    empty_as_zero: bool,
    constraint_series: pd.Series | None = None,
) -> pd.Series:
    """ماسک برداری برای تطبیق مدرسه با رعایت منتورهای global و empty_as_zero."""

    series = ensure_series(mentor_series)
    if pd.api.types.is_integer_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce").astype("Int64")
    else:
        numeric = sanitize_school_series(series)

    numeric = numeric.fillna(0 if empty_as_zero else -1)

    if empty_as_zero and student_school == 0:
        if constraint_series is None:
            return pd.Series(True, index=numeric.index)
        restricted = ensure_series(constraint_series).fillna(False).astype(bool)
        return ~restricted

    base_mask = numeric.eq(0)
    if student_school != 0:
        base_mask = base_mask | numeric.eq(student_school)

    if constraint_series is not None:
        restricted = ensure_series(constraint_series).fillna(False).astype(bool)
        restricted_match = restricted & numeric.eq(student_school)
        unrestricted_match = (~restricted) & base_mask
        base_mask = restricted_match | unrestricted_match

    return base_mask.fillna(False)


def finance_mask_series(
    mentor_series: pd.Series,
    *,
    student_variants: frozenset[int],
    policy: PolicyConfig,
) -> pd.Series:
    """ماسک برداری برای تطبیق مالی با پشتیبانی از variantها."""

    if not student_variants:
        return pd.Series(False, index=mentor_series.index)
    series = ensure_series(mentor_series)
    if pd.api.types.is_integer_dtype(series):
        numeric = pd.to_numeric(series, errors="coerce").astype("Int64")
        return cast(
            pd.Series,
            isin_mask(numeric, student_variants, name="student_variants"),
        ).fillna(False)
    mentor_variants = series.map(lambda cell: finance_variants_from_cell(cell, policy))
    return mentor_variants.map(
        lambda variants: bool(variants and student_variants.intersection(variants))
    )


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
        if _is_group_key(join_key, policy):
            return _canonicalize_group_value(value)
        return _canonicalize_numeric_value(value, allow_zero_from_empty=False)
    except ValueError as exc:
        error_code = "DATA_INVALID"
        if exc.args:
            candidate = str(exc.args[0])
            if candidate in {"DATA_MISSING", "DATA_INVALID"}:
                error_code = candidate
        raise JoinKeyCanonicalizationError(column, value, error_code=error_code) from exc


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
    coerced = _canonicalize_numeric_value(value, allow_zero_from_empty=False)
    if coerced < 0:
        raise ValueError("DATA_MISSING")
    return coerced


def _canonicalize_group_value(value: object) -> int:
    """Canonicalize group code enforcing LAW-valid set."""

    coerced = _canonicalize_numeric_value(value, allow_zero_from_empty=False)
    if coerced not in VALID_GROUP_CODES:
        raise ValueError("DATA_INVALID")
    return coerced


def _canonicalize_school_value(value: object, policy: PolicyConfig) -> int:
    coerced = _canonicalize_numeric_value(
        value, allow_zero_from_empty=policy.school_code_empty_as_zero
    )
    if coerced < 0:
        raise ValueError("DATA_MISSING")
    return coerced


def normalize_join_key_name(column: str) -> str:
    """Normalize join-key names to the underscore form used in join_map."""

    return column.replace(" ", "_")


def parse_group_codes(
    raw: object,
    *,
    valid_codes: Iterable[int] | None = None,
    invalid_collector: list[int] | None = None,
) -> list[int]:
    """Parse ``شامل گروه های آزمایشی`` style specs into validated group codes."""

    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    text = normalize_digits(str(raw)).strip()
    if not text:
        return []
    tokens = _RE_SPLIT_ITEMS.split(text.replace("-", ":"))
    effective_valid = (
        VALID_GROUP_CODES if valid_codes is None else tuple(int(v) for v in valid_codes)
    )
    valid_set = set(int(v) for v in effective_valid)
    seen_valid: set[int] = set()
    invalid_seen: set[int] = set()

    def _digits_only(value: str) -> str:
        return "".join(ch for ch in value if ch.isdigit())

    def _register(value: int) -> None:
        if value in valid_set:
            seen_valid.add(value)
        elif invalid_collector is not None and value not in invalid_seen:
            invalid_collector.append(value)
            invalid_seen.add(value)

    for token in tokens:
        token = token.strip().replace("-", ":")
        if not token:
            continue
        if ":" in token:
            start, end = token.split(":", 1)
            start_digits, end_digits = _digits_only(start), _digits_only(end)
            if not start_digits or not end_digits:
                continue
            a, b = int(start_digits), int(end_digits)
            if a > b:
                a, b = b, a
            for value in range(a, b + 1):
                _register(value)
            continue

        digits_only = _digits_only(token)
        if digits_only:
            _register(int(digits_only))

    return sorted(seen_valid)


def validate_and_canonicalize_join_keys(
    df_raw: pd.DataFrame,
    *,
    policy: PolicyConfig,
    entity_type: JoinKeyEntityType,
    progress: Callable[[int, str], None] | None = None,
) -> JoinKeyValidationResult:
    """Validate join keys for a raw DataFrame and return canonical/invalid splits.

    The function never raises for data-quality issues; instead, it collects
    :class:`JoinKeyValidationIssue` entries for rows containing missing or invalid
    join-key values. Only fully valid rows are propagated to ``canonical_df``.
    """

    issues: list[JoinKeyValidationIssue] = []
    join_key_columns = list(policy.join_keys)
    total_rows = len(df_raw)
    canonical_df = df_raw.copy(deep=True)
    row_positions = pd.Series(range(total_rows), index=df_raw.index)
    valid_mask = pd.Series(True, index=df_raw.index)

    for column in join_key_columns:
        if column not in canonical_df.columns:
            canonical_df[column] = pd.NA
            for row_index, offset in row_positions.items():
                issues.append(
                    JoinKeyValidationIssue(
                        entity_type=entity_type,
                        row_index=int(offset),
                        column=column,
                        raw_value=None,
                        error_code="MISSING_COLUMN",
                    )
                )
            valid_mask[:] = False
            continue

        candidate = canonical_df[column]
        if isinstance(candidate, pd.DataFrame):
            series = candidate.iloc[:, -1].copy()
            canonical_df = canonical_df.drop(columns=column)
            canonical_df[column] = series
        else:
            series = candidate.copy()

        conversion = series.apply(
            lambda value: _canonicalize_join_key_value_safe(column, value, policy=policy)
        )
        coerced = conversion.apply(lambda pair: pair[0])
        errors = conversion.apply(lambda pair: pair[1])

        error_mask = errors.notna()
        if error_mask.any():
            for row_index, raw_value, error_code in zip(
                series.index[error_mask],
                series[error_mask],
                errors[error_mask],
                strict=False,
            ):
                issues.append(
                    JoinKeyValidationIssue(
                        entity_type=entity_type,
                        row_index=int(row_positions[row_index]),
                        column=column,
                        raw_value=raw_value,
                        error_code=str(error_code),
                    )
                )
            valid_mask.loc[error_mask] = False

        canonical_df[column] = coerced

    canonical_df = canonical_df.loc[valid_mask].reset_index(drop=True)
    for column in join_key_columns:
        canonical_df[column] = canonical_df[column].astype("Int64")

    if progress is not None and total_rows:
        for offset in range(total_rows):
            pct = int(((offset + 1) / total_rows) * 100)
            progress(pct, "validated join keys")
    return JoinKeyValidationResult(canonical_df=canonical_df, issues=issues)


def assert_canonical_join_keys(df: pd.DataFrame, policy: PolicyConfig) -> None:
    """Assert that a DataFrame carries fully canonical join-key columns.

    The check is intended for internal Core usage to prevent accidental invocation
    of Core algorithms with unvalidated data.
    """

    join_key_columns = list(policy.join_keys)
    missing = [column for column in join_key_columns if column not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing join-key columns: {missing}")
    for column in join_key_columns:
        series = df[column]
        if series.isna().any():
            raise ValueError(f"Join-key column '{column}' contains null values")
        if not pd.api.types.is_integer_dtype(series.dtype):
            raise ValueError(f"Join-key column '{column}' must be integer typed")


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

_RE_SPLIT_ITEMS = re.compile(r"[,\u060C\s]+")


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
    """Compare centers using mentor-side-only wildcard semantics.

    Per v3 semantics, only mentor_center == 0 is treated as the wildcard.
    The wildcard_center parameter is retained for backward compatibility.
    """

    if mentor_center == 0:
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
            if wildcard_center is not None and student_int == int(wildcard_center):
                continue
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
