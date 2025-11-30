"""ماژول تخصیص دانش‌آموز به پشتیبان مطابق Policy-First و LAW v3.0."""

from __future__ import annotations

import math
import warnings
from collections.abc import Callable, Hashable, Mapping, Sequence
from dataclasses import dataclass
from numbers import Number, Real
from typing import Any, Literal, SupportsFloat, SupportsInt, TypedDict, TypeVar, cast

import pandas as pd
from pandas.api import types as pd_types

from .allocation.trace import attach_allocation_channel
from .canonical_frames import canonicalize_pool_frame, canonicalize_students_frame
from .center_manager import resolve_center_manager_config, validate_center_config
from .common.columns import CANON_EN_TO_FA, canonicalize_headers, dedupe_columns, ensure_series
from .common.filters import (
    StudentSchoolCode,
    apply_join_filters,
    resolve_student_school_code,
)
from .common.ids import build_mentor_id_map, inject_mentor_id, natural_key
from .common.join_keys import (
    JoinKeyCanonicalizationError,
    canonicalize_join_key_value,
    center_wildcard_value,
    finance_variants_from_cell,
    normalize_join_key_name as _normalize_join_key_name,
    resolve_finance_variants,
    validate_selected_mentor_join_keys,
)
from .common.ranking import (
    MentorCapacityState,
    apply_ranking_policy,
    build_mentor_state,
    consume_capacity,
)
from .common.reasons import ReasonCode, build_reason
from .common.rules import (
    CenterPriorityRule,
    Rule,
    RuleEngine,
    SchoolStudentPriorityGuard,
    default_stage_rule_map,
)
from .common.trace import (
    TraceOutcome,
    TraceStagePlan,
    build_allocation_trace,
    build_trace_plan,
    build_unallocated_summary,
    find_allocation_policy_violations,
    summarize_trace_outcome,
)
from .common.types import (
    CANONICAL_TRACE_ORDER,
    AllocationAlertRecord,
    AllocationErrorLiteral,
    AllocationLogRecord,
    JoinKeyValues,
    MentorStateDelta,
    MentorStateSnapshot,
    StudentRow,
    TraceStageLiteral,
    TraceStageName,
    TraceStageRecord,
    ensure_trace_stage_name,
)
from .counter import normalize_digits, strip_hidden_chars
from .policy_loader import PolicyConfig, load_policy
from .reason.selection_reason import build_selection_reason_rows as _build_selection_reason_rows

ProgressFn = Callable[[int, str], None]


class JoinMismatch(TypedDict):
    column: str
    student_value: object
    mentor_values: list[object]
    reason: str


__all__ = [
    "ProgressFn",
    "AllocationResult",
    "allocate_student",
    "allocate_batch",
    "build_selection_reason_rows",
]

_STUDENT_NATIONAL_KEYS: tuple[str, ...] = (
    "student_national_code",
    "student_national_id",
    "national_id",
    "کدملی دانش‌آموز",
    "کدملی",
    "کد ملی",
)

_MENTOR_ALIAS_KEYS: tuple[str, ...] = (
    "mentor_alias_code",
    "mentor_alias_postal_code",
    "mentor_postal_code",
    "alias",
    "alias_norm",
    "alias_normal",
    "جایگزین",
    "جایگزین | alias",
    "کد جایگزین پشتیبان",
    "کدپستی",
    "کد پستی",
)

_ALLOCATION_OUTPUT_COLUMNS: tuple[str, ...] = (
    "student_id",
    "student_national_code",
    "mentor",
    "mentor_id",
    "mentor_alias_code",
)

_JOIN_STAGE_FAILURE_ORDER: tuple[TraceStageLiteral, ...] = (
    "type",
    "group",
    "gender",
    "graduation_status",
    "center",
    "finance",
    "school",
)

_STAGE_LABEL_FA: dict[str, str] = {
    "type": CANON_EN_TO_FA.get("group_code", "type"),
    "group": CANON_EN_TO_FA.get("exam_group", "group"),
    "gender": CANON_EN_TO_FA.get("gender", "gender"),
    "graduation_status": CANON_EN_TO_FA.get("graduation_status", "graduation_status"),
    "center": CANON_EN_TO_FA.get("center", "center"),
    "finance": CANON_EN_TO_FA.get("finance", "finance"),
    "school": CANON_EN_TO_FA.get("school_code", "school"),
    "capacity_gate": "capacity",
}

T = TypeVar("T")
HeaderMode = Literal["fa", "en", "fa_en"]


def safe_int(value: Any) -> int | None:
    """تبدیل امن انواع مختلف به int با هندل کردن pandas NaN و None."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, complex):
        return None
    if isinstance(value, Real):
        return int(float(value))
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return int(float(cleaned))
        except ValueError:
            return None
    if isinstance(value, pd.Timestamp):
        return int(value.timestamp())
    return None


# ✅ این تابع اصلاح شده و بدون خطا است
def safe_float(value: Any) -> float | None:
    """تبدیل امن انواع مختلف به float."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, Number):
        if isinstance(value, complex):
            return None
        return float(cast(SupportsFloat, value))
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def safe_str(value: Any) -> str | None:
    """تبدیل امن به رشته با هندل کردن None و NaN."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return str(value).strip() or None


def _normalize_digit_code(
    value: object,
    *,
    length: int | None = None,
    pad: bool = False,
    allow_shorter: bool = False,
) -> str:
    """نرمال‌سازی ورودی‌های عددی به رشتهٔ digits پایدار برای خروجی اکسل."""
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    text = strip_hidden_chars(normalize_digits(str(value).strip()))
    if not text:
        return ""
    digits = "".join(ch for ch in text if ch.isdigit())
    if not digits:
        return ""
    if length is not None:
        if len(digits) > length:
            digits = digits[-length:]
        if pad:
            digits = digits.zfill(length)
        elif len(digits) < length and not allow_shorter:
            return ""
    return digits


def _extract_student_national_code(student: Mapping[str, object]) -> str:
    """بازیابی امن کد ملی دانش‌آموز از کلیدهای چندزبانهٔ ورودی."""
    for key in _STUDENT_NATIONAL_KEYS:
        value = student.get(key)
        normalized = _normalize_digit_code(value, length=10, pad=True)
        if normalized:
            return normalized
    return ""


def _extract_mentor_alias_code(mentor_row: Mapping[str, object] | pd.Series) -> str:
    """دریافت کد جایگزین/پستی پشتیبان با حذف نویز ورودی."""
    for key in _MENTOR_ALIAS_KEYS:
        value = mentor_row.get(key)
        normalized = _normalize_digit_code(value, length=10, allow_shorter=True)
        if normalized:
            trimmed = normalized.lstrip("0")
            if trimmed:
                return trimmed
    return ""


def _normalize_mentor_identifier(value: object) -> str | None:
    """تبدیل امن شناسهٔ پشتیبان به مقدار قابل جست‌وجو در state."""
    if value is None:
        return None
    if isinstance(value, pd.Series):
        if value.empty:
            return None
        return _normalize_mentor_identifier(value.iloc[0])
    if isinstance(value, pd.DataFrame):
        if value.empty:
            return None
        return _normalize_mentor_identifier(value.iloc[0])
    if isinstance(value, (list, tuple, set, dict)):
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    if isinstance(value, str):
        normalized = value.strip()
        return normalized or None
    return str(value).strip() or None


def _resolve_mentor_identifier(result: AllocationResult, *, policy: PolicyConfig) -> str:
    """بازیابی شناسهٔ پشتیبان با اولویت: log → سطر فارسی → سطر canonical."""
    mentor_identifier_logged = _normalize_mentor_identifier(result.log.get("mentor_id"))
    if mentor_identifier_logged is not None:
        result.log["mentor_id"] = mentor_identifier_logged
        return mentor_identifier_logged
    if result.mentor_row is None:
        raise KeyError("Mentor identifier missing: row not provided")
    mentor_identifier = _normalize_mentor_identifier(result.mentor_row.get("کد کارمندی پشتیبان"))
    if mentor_identifier is not None:
        result.log["mentor_id"] = mentor_identifier
        return mentor_identifier
    mentor_row_en = canonicalize_headers(
        result.mentor_row.to_frame().T,
        header_mode=cast(HeaderMode, policy.excel.header_mode_internal),
    ).iloc[0]
    mentor_identifier = _normalize_mentor_identifier(mentor_row_en.get("mentor_id"))
    if mentor_identifier is not None:
        result.log["mentor_id"] = mentor_identifier
        return mentor_identifier
    raise KeyError("Mentor identifier missing from allocation log and row")


def _noop_progress(_: int, __: str) -> None:
    """تابع پیش‌فرض progress که کاری انجام نمی‌دهد."""


@dataclass(frozen=True)
class AllocationResult:
    """خروجی تخصیص یک دانش‌آموز مطابق §5 Technical SSoT."""

    mentor_row: pd.Series | None
    trace: list[TraceStageRecord]
    log: AllocationLogRecord


@dataclass(frozen=True)
class StudentCenterInfo:
    """اطلاعات استخراج‌شده از ستون مرکز برای یک دانش‌آموز."""

    column: str
    raw_value: object | None
    normalized_value: int | None
    is_invalid: bool


def _maybe_int_from_text(value: object) -> int | None:
    """تبدیل امن ورودی‌های متنوع به شناسه عددی پایدار."""
    try:
        numeric = pd.to_numeric([value], errors="coerce")[0]
    except Exception:
        return None
    if isinstance(numeric, Real):
        if isinstance(numeric, float):
            if float(numeric).is_integer():
                return int(numeric)
            return None
        return int(cast(SupportsInt, numeric))
    if pd.isna(numeric):
        return None
    return None


def _resolve_mentor_state_entry(
    mentor_state: Mapping[str, MentorCapacityState],
    identifier: str | None,
) -> tuple[str | None, MentorCapacityState | None]:
    """Resolve mentor state entry while tolerating minor formatting mismatches."""
    if identifier is None:
        return None, None
    candidates: list[str] = []
    seen: set[str] = set()

    def _push(value: str | None) -> None:
        if value is None:
            return
        marker = value.strip()
        if not marker or marker in seen:
            return
        seen.add(marker)
        candidates.append(marker)

    _push(identifier)
    numeric_candidate = _maybe_int_from_text(identifier)
    if numeric_candidate is not None:
        _push(str(numeric_candidate))
    for candidate in candidates:
        entry = mentor_state.get(candidate)
        if entry is not None:
            return candidate, entry
    return None, None


def _stringify_mentor_state(
    mentor_state: Mapping[Any, MentorCapacityState],
) -> dict[str, MentorCapacityState]:
    """نرمال‌سازی کلیدهای state پشتیبان به رشته پایدار."""
    normalized: dict[str, MentorCapacityState] = {}
    for key, value in mentor_state.items():
        normalized_key = _normalize_mentor_identifier(key)
        if normalized_key is None:
            continue
        normalized[normalized_key] = value
    return normalized


def _safe_state_int(value: object) -> int:
    """تبدیل امن ورودی‌های متنوع ظرفیت به int پایدار."""
    if isinstance(value, Number):
        try:
            if pd.isna(value):
                return 0
        except TypeError:
            pass
        if isinstance(value, complex):
            return 0
        return int(cast(SupportsInt, value))
    text = str(value or "").strip()
    if not text:
        return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def _safe_state_float(value: object) -> float:
    """تبدیل عمومی مقادیر occupancy_ratio به float."""
    if isinstance(value, Number):
        try:
            if pd.isna(value):
                return 0.0
        except TypeError:
            pass
        if isinstance(value, complex):
            return 0.0
        return float(cast(SupportsFloat, value))
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except Exception:
        return 0.0


def _snapshot_state_entry(
    entry: Mapping[str, Any] | None,
) -> MentorStateSnapshot:
    """ساخت snapshot قابل‌اعتماد از وضعیت پشتیبان برای ثبت تغییرات."""
    source = entry or {}
    snapshot: MentorStateSnapshot = {
        "remaining": _safe_state_int(source.get("remaining")),
        "alloc_new": _safe_state_int(source.get("alloc_new")),
        "occupancy_ratio": _safe_state_float(source.get("occupancy_ratio")),
    }
    return snapshot


def _build_state_delta(before: MentorStateSnapshot, after: MentorStateSnapshot) -> MentorStateDelta:
    """محاسبهٔ diff بین دو snapshot برای استفاده در ExplainAgent."""
    diff: MentorStateSnapshot = {
        "remaining": after["remaining"] - before["remaining"],
        "alloc_new": after["alloc_new"] - before["alloc_new"],
        "occupancy_ratio": after["occupancy_ratio"] - before["occupancy_ratio"],
    }
    return {
        "before": before,
        "after": after,
        "diff": diff,
    }


class JoinKeyDataMissingError(ValueError):
    """خطای اختصاصی برای کمبود دادهٔ کلیدهای Join در ورودی دانش‌آموز."""

    def __init__(self, missing_columns: Sequence[str], join_map: Mapping[str, int]) -> None:
        super().__init__("DATA_MISSING")
        self.missing_columns: tuple[str, ...] = tuple(missing_columns)
        self.join_map: dict[str, int] = dict(join_map)


class JoinKeyDataInvalidError(ValueError):
    """خطای اختصاصی برای مقادیر نامعتبر کلیدهای Join."""

    def __init__(self, column: str, value: object, join_map: Mapping[str, int]) -> None:
        super().__init__("DATA_MISSING")
        self.column = column
        self.value = value
        self.join_map: dict[str, int] = dict(join_map)


def _resolve_capacity_column(policy: PolicyConfig, override: str | None) -> str:
    """تعیین ستون ظرفیت با اولویت override سپس policy."""
    if override:
        return override
    try:
        return policy.stage_column("capacity_gate")
    except KeyError:
        return policy.columns.remaining_capacity


def _canonical_stage_counts(
    stage_candidate_counts: Mapping[str, int] | Mapping[TraceStageName, int],
) -> dict[TraceStageName, int]:
    """بازگردانی شمارنده‌ها روی ترتیب ۸ مرحلهٔ استاندارد."""
    return {stage: int(stage_candidate_counts.get(stage, 0)) for stage in CANONICAL_TRACE_ORDER}


def _derive_error_type_from_stage_counts(
    stage_candidate_counts: Mapping[TraceStageName, int],
) -> AllocationErrorLiteral:
    """طبقه‌بندی خطا براساس شمارندهٔ مراحل Trace با بهبود برای BUG_ERR_01."""
    canonical = _canonical_stage_counts(stage_candidate_counts)
    # تفکیک خطاهای join از خطاهای ظرفیت
    join_stages = CANONICAL_TRACE_ORDER[:-1]  # همه مراحل به جز capacity_gate
    capacity_stage = CANONICAL_TRACE_ORDER[-1]

    # اگر در هر یک از مراحل join تعداد کاندید صفر شود
    if any(canonical.get(stage, 0) == 0 for stage in join_stages):
        return "ELIGIBILITY_NO_MATCH"
    # اگر در مرحله ظرفیت صفر شود ولی مراحل قبل کاندید داشتند
    if canonical.get(capacity_stage, 0) == 0:
        return "CAPACITY_FULL"
    return "INTERNAL_ERROR"


def _center_mask_series(
    mentor_series: pd.Series,
    student_center: int,
    wildcard_center: int | None,
) -> pd.Series:
    """ماسک برداری برای تطبیق مرکز با پشتیبانی wildcard مطابق §6.3 Technical SSoT."""
    series = ensure_series(mentor_series)
    try:
        numeric = pd.to_numeric(series, errors="coerce").astype("Int64")
    except (TypeError, ValueError):
        numeric = series

    if not pd_types.is_integer_dtype(numeric):
        numeric = pd.to_numeric(numeric, errors="coerce").astype("Int64")

    wildcard_values: set[int] = {int(wildcard_center)} if wildcard_center is not None else {0}

    if student_center in wildcard_values:
        return pd.Series(True, index=numeric.index)

    wildcard_mask = numeric.isin(wildcard_values)
    mentor_mask = numeric.eq(student_center) | wildcard_mask
    return mentor_mask.fillna(False)


def _school_mask_series(
    mentor_series: pd.Series,
    student_school: int,
    empty_as_zero: bool,
    constraint_series: pd.Series | None = None,
) -> pd.Series:
    """ماسک برداری برای تطبیق مدرسه با رعایت منتورهای global و empty_as_zero مطابق §6.3 Technical SSoT."""
    series = ensure_series(mentor_series)
    try:
        # خالی/NaN به‌عنوان ۰ (global) در نظر گرفته می‌شود اگر empty_as_zero=True باشد،
        # در غیر این صورت به مقدار نامعتبر -1 نگاشت می‌شود تا match نشود
        series = series.fillna(0) if empty_as_zero else series.fillna(-1)
    except Exception:
        series = mentor_series

    # اگر empty_as_zero و مدرسه‌ی دانش‌آموز ۰ است، یعنی «بدون محدودیت مدرسه‌ای»
    # در این حالت فقط constraint (has_school_constraint) اعمال می‌شود.
    if empty_as_zero and student_school == 0:
        if constraint_series is None:
            return pd.Series(True, index=series.index)
        restricted = ensure_series(constraint_series).fillna(False).astype(bool)
        return ~restricted

    # منتورهای global
    base_mask = series.eq(0)
    # اگر دانش‌آموز مدرسهٔ مشخصی دارد، همان مدرسه نیز مجاز است
    if student_school != 0:
        school_mask = series.eq(student_school)
        base_mask = base_mask | school_mask

    # اگر constraint تعریف شده، منتورهای restricted حذف می‌شوند
    if constraint_series is not None:
        restricted = ensure_series(constraint_series).fillna(False).astype(bool)
        restricted_match = restricted & series.eq(student_school)
        unrestricted_match = (~restricted) & base_mask
        base_mask = restricted_match | unrestricted_match

    return base_mask


def _canonicalize_gender_series(series: pd.Series, policy: PolicyConfig) -> pd.Series:
    """نرمال‌سازی سری جنسیت منتورها به کد عددی Policy با بهبود برای BUG_GND_01."""

    def _normalize(value: object) -> int | None:
        # تبدیل جنسیت فارسی به کد عددی
        if isinstance(value, str):
            value = value.strip()
            if value == "پسر":
                return 1
            if value == "دختر":
                return 0
        try:
            return canonicalize_join_key_value(policy.stage_column("gender"), value, policy=policy)
        except JoinKeyCanonicalizationError:
            return None

    normalized = series.map(_normalize)
    return pd.Series(normalized, index=series.index, dtype="Int64")


def _normalize_mismatch_scalar(value: object) -> object:
    """نرمال‌سازی مقدار برای گزارش مغایرت."""
    if value is None:
        return None
    if value is pd.NA:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, SupportsInt):
        return int(value)
    if isinstance(value, Real):
        return int(float(cast(SupportsFloat, value)))
    return value


def _sort_key_for_mismatch_value(value: object) -> tuple[int, str]:
    """کلید مرتب‌سازی برای مقادیر مغایرت."""
    if value is None:
        return (0, "")
    return (1, str(value))


def _normalize_mismatch_entry(entry: Mapping[str, object]) -> JoinMismatch:
    """نرمال‌سازی ورودی مغایرت برای گزارش یکپارچه."""
    column = str(entry.get("column", ""))
    reason = str(entry.get("reason", ""))
    student_value = _normalize_mismatch_scalar(entry.get("student_value"))
    raw_mentor_values = entry.get("mentor_values")
    mentor_values: list[object]
    if isinstance(raw_mentor_values, Sequence) and not isinstance(
        raw_mentor_values,
        (str, bytes),
    ):
        mentor_values = [_normalize_mismatch_scalar(value) for value in raw_mentor_values]
    elif raw_mentor_values is None:
        mentor_values = []
    else:
        mentor_values = [_normalize_mismatch_scalar(raw_mentor_values)]
    mentor_values_sorted = sorted(
        dict.fromkeys(mentor_values),
        key=_sort_key_for_mismatch_value,
    )
    return {
        "column": column,
        "reason": reason,
        "student_value": student_value,
        "mentor_values": mentor_values_sorted,
    }


def _merge_join_mismatches(
    primary: Sequence[Mapping[str, object]],
    secondary: Sequence[Mapping[str, object]],
) -> list[JoinMismatch]:
    """ترکیب مغایرت‌های join با حذف موارد تکراری و ترتیب پایدار."""
    normalized_entries = [_normalize_mismatch_entry(entry) for entry in (*primary, *secondary)]
    dedup: dict[tuple[str, str, object, tuple[object, ...]], JoinMismatch] = {}
    for entry in normalized_entries:
        key = (
            entry["column"],
            entry["reason"],
            entry["student_value"],
            tuple(entry["mentor_values"]),
        )
        if key not in dedup:
            dedup[key] = entry

    def _sort_key(
        entry: JoinMismatch,
    ) -> tuple[str, str, tuple[int, str], tuple[tuple[int, str], ...]]:
        student_sort = _sort_key_for_mismatch_value(entry["student_value"])
        mentor_sort = tuple(_sort_key_for_mismatch_value(value) for value in entry["mentor_values"])
        return (entry["column"], entry["reason"], student_sort, mentor_sort)

    return sorted(dedup.values(), key=_sort_key)


def _filter_candidates_by_join_map(
    candidates: pd.DataFrame,
    *,
    join_map: Mapping[str, int],
    policy: PolicyConfig,
) -> tuple[pd.DataFrame, list[JoinMismatch]]:
    """اعمال فیلتر تطابق کامل ۶ کلید join روی استخر کاندید."""
    if candidates.empty:
        return candidates, []
    mask = pd.Series(True, index=candidates.index)
    mismatches: list[JoinMismatch] = []
    center_wildcard = center_wildcard_value(policy)

    for column in policy.join_keys:
        normalized = _normalize_join_key_name(column)
        student_value = join_map.get(normalized)
        if student_value is None:
            mask &= False
            mismatches.append(
                {
                    "column": column,
                    "student_value": None,
                    "mentor_values": [],
                    "reason": "student_join_key_missing",
                }
            )
            continue
        if column not in candidates.columns:
            mask &= False
            mismatches.append(
                {
                    "column": column,
                    "student_value": student_value,
                    "mentor_values": [],
                    "reason": "mentor_column_missing",
                }
            )
            continue

        mentor_series_raw = ensure_series(candidates[column])

        if column == policy.stage_column("center"):
            mentor_series = pd.to_numeric(mentor_series_raw, errors="coerce").astype("Int64")
            col_mask = _center_mask_series(mentor_series, int(student_value), center_wildcard)
        elif column == policy.columns.school_code:
            school_constraint = (
                ensure_series(candidates.get("has_school_constraint"))
                if "has_school_constraint" in candidates.columns
                else None
            )
            mentor_series = pd.to_numeric(mentor_series_raw, errors="coerce").astype("Int64")
            col_mask = _school_mask_series(
                mentor_series,
                int(student_value),
                policy.school_code_empty_as_zero,
                school_constraint,
            )
        elif column == policy.stage_column("finance"):
            # بهبود برای BUG_FNC_01 - استفاده از variants مالی
            allowed_finance = resolve_finance_variants(int(student_value), policy)
            mentor_variants = mentor_series_raw.map(
                lambda cell: finance_variants_from_cell(cell, policy)
            )
            col_mask = mentor_variants.map(
                lambda variants: bool(allowed_finance.intersection(variants)) if variants else False
            )
        else:
            if column == policy.stage_column("gender"):
                mentor_series = _canonicalize_gender_series(mentor_series_raw, policy)
            else:
                mentor_series = pd.to_numeric(mentor_series_raw, errors="coerce").astype("Int64")
            col_mask = mentor_series == int(student_value)

        mask &= col_mask.fillna(False)

        if not bool(col_mask.all()):
            mentor_sample = mentor_series.loc[~col_mask].dropna().unique().tolist()[:5]
            mismatches.append(
                {
                    "column": column,
                    "student_value": student_value,
                    "mentor_values": mentor_sample,
                    "reason": "mentor_value_mismatch",
                }
            )

    filtered = candidates.loc[mask]
    return filtered, mismatches


def _student_value(student: Mapping[str, object], column: str) -> object:
    """استخراج مقدار دانش‌آموز از ستون با پشتیبانی از نام‌های مختلف."""
    if column in student:
        return student[column]
    normalized = column.replace(" ", "_")
    if normalized in student:
        return student[normalized]
    raise KeyError(f"Student row missing value for '{column}'")


def _is_missing_join_value(value: object) -> bool:
    """تشخیص تهی بودن مقدار کلید join برای ثبت DATA_MISSING."""

    if value is None:
        return True
    try:
        if isinstance(value, Number) and pd.isna(value):
            return True
    except TypeError:
        return False
    if isinstance(value, str):
        return not normalize_digits(value).strip()
    return False


def _resolve_student_center_info(
    student: Mapping[str, object],
    policy: PolicyConfig,
) -> StudentCenterInfo:
    """استخراج ستون مرکز و تشخیص معتبر بودن مقدار."""
    column = policy.stage_column("center")
    raw_column = "center_raw"
    candidates = (
        raw_column,
        column,
        column.replace(" ", "_"),
        CANON_EN_TO_FA.get("center", "center"),
        "center",
    )
    value: object | None = None
    source = column
    for candidate in candidates:
        if candidate in student:
            value = student[candidate]
            source = candidate
            break
    normalized = _maybe_int_from_text(value)
    text_value = str(value).strip() if isinstance(value, str) else value
    is_invalid = bool(
        value is None or (isinstance(text_value, str) and not text_value) or normalized is None,
    )
    return StudentCenterInfo(
        column=str(source),
        raw_value=value,
        normalized_value=normalized,
        is_invalid=is_invalid,
    )


def _extract_and_validate_center(
    student: Mapping[str, object],
    policy: PolicyConfig,
) -> tuple[int | None, bool]:
    """استخراج مقدار مرکز دانش‌آموز و تشخیص معتبر بودن آن."""
    column = policy.stage_column("center")
    fallback_center = getattr(policy, "default_center_for_invalid", None)
    try:
        value = _student_value(student, column)
    except KeyError:
        return fallback_center, False
    try:
        if value is None or value == "":
            return fallback_center, False
        if isinstance(value, str):
            text_value = value.strip()
            if not text_value:
                return fallback_center, False
            value = text_value
        if pd.isna(value):
            return fallback_center, False
    except Exception:
        return fallback_center, False
    numeric_value = _maybe_int_from_text(value)
    if numeric_value is None:
        return fallback_center, False
    return numeric_value, True


def _collect_join_key_map(
    student: Mapping[str, object],
    policy: PolicyConfig,
) -> tuple[dict[str, int], tuple[str, ...]]:
    """جمع‌آوری نگاشت کلیدهای join با بهبود برای باگ‌های GND_01, GRP_01, FNC_01."""
    join_map: dict[str, int] = {}
    missing_columns: list[str] = []
    invalid_map: dict[str, object] = {}
    school_column = policy.columns.school_code
    # بهبود برای BUG_GRP_01 - استفاده از crosswalk برای کدرشته
    group_crosswalk = getattr(policy, "group_crosswalk", {})
    school_code_resolved: StudentSchoolCode | None = None

    for column in policy.join_keys:
        normalized = _normalize_join_key_name(column)
        allow_zero = policy.school_code_empty_as_zero and column == school_column
        if allow_zero:
            if school_code_resolved is None:
                school_code_resolved = resolve_student_school_code(student, policy)
            school_code = school_code_resolved
            if school_code.missing:
                join_map[normalized] = 0
            else:
                join_map[normalized] = int(school_code.value or 0)
            continue
        try:
            value = _student_value(student, column)
        except KeyError:
            join_map[normalized] = -1
            missing_columns.append(column)
            continue
        if _is_missing_join_value(value):
            join_map[normalized] = -1
            missing_columns.append(column)
            continue
        try:
            # بهبود برای BUG_GND_01 - هندل کردن جنسیت فارسی
            if column == policy.stage_column("gender"):
                if isinstance(value, str):
                    value = value.strip()
                    if value == "پسر":
                        value = 1
                    elif value == "دختر":
                        value = 0
                    else:
                        value = canonicalize_join_key_value(column, value, policy=policy)
                else:
                    value = canonicalize_join_key_value(column, value, policy=policy)
            # بهبود برای BUG_GRP_01 - استفاده از crosswalk
            elif column == policy.stage_column("group") and group_crosswalk:
                raw_value = canonicalize_join_key_value(column, value, policy=policy)
                value = group_crosswalk.get(raw_value, raw_value)
            else:
                value = canonicalize_join_key_value(column, value, policy=policy)
            join_map[normalized] = value
        except JoinKeyCanonicalizationError as exc:
            join_map[normalized] = 0 if allow_zero else -1
            invalid_map[column] = exc.value
            continue

    if invalid_map:
        for column in policy.join_keys:
            normalized = _normalize_join_key_name(column)
            if normalized not in join_map:
                join_map[normalized] = 0 if column == school_column else -1
        column, invalid_value = next(iter(invalid_map.items()))
        raise JoinKeyDataInvalidError(column, invalid_value, join_map)

    return join_map, tuple(missing_columns)


def _build_log_from_join_map(
    student: Mapping[str, object],
    join_map: Mapping[str, int],
) -> AllocationLogRecord:
    """ساخت لاگ پایه از روی نگاشت join keys."""
    log: AllocationLogRecord = {
        "row_index": -1,
        "student_id": str(student.get("student_id", "")),
        "allocation_status": "failed",
        "mentor_selected": None,
        "mentor_id": None,
        "occupancy_ratio": None,
        "join_keys": JoinKeyValues(join_map, expected_keys=join_map.keys()),
        "candidate_count": 0,
        "selection_reason": None,
        "tie_breakers": {},
        "error_type": None,
        "detailed_reason": None,
        "suggested_actions": [],
        "capacity_before": None,
        "capacity_after": None,
        "mentor_state_delta": None,
        "rule_reason_code": None,
        "rule_reason_text": None,
        "rule_reason_details": None,
        "fairness_reason_code": None,
        "fairness_reason_text": None,
        "alerts": [],
        "alias_autofill": 0,
        "alias_unmatched": 0,
        "phase_rule_trace": [],
    }
    return log


def _phase_guard_source(students: pd.DataFrame, policy: PolicyConfig) -> Sequence[object]:
    """ساخت ورودی بهینه برای Stage Guard فاز مدرسه‌ای/مرکزی."""
    column = policy.center_management.school_student_column
    candidates = (
        column,
        column.replace(" ", "_"),
        "is_school_student",
        "school_status_resolved",
    )
    for name in candidates:
        if name in students.columns:
            series = ensure_series(students[name])
            return list(series.fillna(0))
    return [False] * len(students)


def _phase_stage_extras(
    stage: str,
    pool: pd.DataFrame,
    capacity_column: str,
) -> Mapping[str, Any]:
    """تولید پیام مرحله‌ای ثابت برای Trace Rule Engine."""
    if stage == "school_phase_start":
        return {"message": "شروع فاز مدرسه‌ای"}
    if stage == "center_phase_start" and capacity_column in pool.columns:
        remaining = pd.to_numeric(pool[capacity_column], errors="coerce").fillna(0)
        return {
            "message": "شروع فاز مرکزی پس از اتمام مدرسه‌ای",
            "remaining_capacity": int(remaining.sum()),
        }
    return {}


def _build_phase_rule_engines(policy: PolicyConfig) -> tuple[RuleEngine, RuleEngine]:
    """ساخت Rule Engine های فاز مدرسه‌ای و مرکزی براساس Policy."""
    if not policy.center_management.enabled:
        return RuleEngine(), RuleEngine()
    column = policy.center_management.school_student_column
    school_engine = RuleEngine(stage_guards=(SchoolStudentPriorityGuard(column),))
    center_guards = (SchoolStudentPriorityGuard(column),)
    pair_rules: tuple[CenterPriorityRule, ...]
    if policy.center_management.centers:
        pair_rules = (
            CenterPriorityRule(
                center_priority=policy.center_management.priority_order,
                center_column=policy.stage_column("center"),
            ),
        )
    else:
        pair_rules = ()
    center_engine = RuleEngine(stage_guards=center_guards, pair_rules=pair_rules)
    return school_engine, center_engine


def _phase_reason_message(reason: ReasonCode) -> str:
    """متن فارسی پایدار برای رویدادهای Trace فازها."""
    if reason is ReasonCode.SCHOOL_STUDENT_PRIORITY:
        return "تخصیص به پشتیبان مدرسه‌ای بدون در نظر گرفتن مرکز"
    if reason is ReasonCode.CENTER_MISMATCH:
        return "رد به دلیل عدم تطابق مرکز دانش‌آموز و پشتیبان"
    if reason is ReasonCode.INVALID_CENTER_VALUE:
        return "مرکز نامعتبر به مقدار پیش‌فرض تغییر یافت"
    if reason is ReasonCode.NO_MANAGER_FOR_CENTER:
        return "هیچ مدیری برای این مرکز در استخر موجود نبود"
    return build_reason(reason).message_fa


def _sort_students_by_center_priority(
    students: pd.DataFrame,
    policy: PolicyConfig,
    priority: Sequence[int] | None,
) -> pd.DataFrame:
    """مرتب‌سازی پایدار دانش‌آموزان براساس اولویت مرکز."""
    if not priority:
        return students
    column = policy.stage_column("center")
    candidates = (
        column,
        column.replace(" ", "_"),
        CANON_EN_TO_FA.get("center", "center"),
        "center",
    )
    target_column = next((name for name in candidates if name in students.columns), None)
    if target_column is None:
        raise ValueError("students dataframe missing center column for sorting")
    numeric = pd.to_numeric(students[target_column], errors="coerce")
    fallback_center = policy.default_center_for_invalid
    fill_value = fallback_center if fallback_center is not None else -1
    numeric = numeric.fillna(fill_value).astype(int)
    order_map = {int(value): idx for idx, value in enumerate(priority)}
    fallback = len(order_map)
    order = numeric.map(lambda x: order_map.get(int(x), fallback))
    sorted_students = students.assign(__center_order__=order)
    by_columns = ["__center_order__"]
    if "student_id" in sorted_students.columns:
        by_columns.append("student_id")
    sorted_students = sorted_students.sort_values(by=by_columns, kind="stable")
    return sorted_students.drop(columns=["__center_order__"])


def _separate_school_students(
    students: pd.DataFrame,
    policy: PolicyConfig,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """جداسازی دانش‌آموزان مدرسه‌ای از مرکزی بر اساس ستون مشخص در Policy."""
    column_candidates: list[str] = []
    school_column = policy.center_management.school_student_column
    if school_column:
        column_candidates.append(school_column)
    if "school_status_resolved" not in column_candidates:
        column_candidates.append("school_status_resolved")
    column = next((col for col in column_candidates if col in students.columns), None)
    if column is None:
        empty = students.iloc[0:0].copy()
        return empty, students.copy()

    series = students[column]
    if pd_types.is_bool_dtype(series):
        school_mask = series.fillna(False).astype(bool)
    else:
        statuses = {int(value) for value in policy.school_statuses}
        values = pd.to_numeric(series, errors="coerce").fillna(0).astype(int)
        school_mask = values.isin(statuses)

    school_students = students.loc[school_mask].copy()
    center_students = students.loc[~school_mask].copy()
    return school_students, center_students


def _build_center_manager_index(
    pool: pd.DataFrame,
    policy: PolicyConfig,
    manager_map: Mapping[int, Sequence[str]] | None,
    *,
    strict_validation: bool = False,
) -> tuple[dict[int, pd.Index], list[int]]:
    """ساخت نگاشت مرکز → ایندکس منتورها با گزارش مراکز بدون مدیر."""
    if not manager_map:
        return {}, []
    center_candidates = (
        policy.stage_column("center"),
        policy.stage_column("center").replace(" ", "_"),
        CANON_EN_TO_FA.get("center", "center"),
        "center",
    )
    center_column = next((name for name in center_candidates if name in pool.columns), None)
    manager_candidates = (
        CANON_EN_TO_FA.get("manager_name", "مدیر"),
        "manager_name",
    )
    manager_column = next((name for name in manager_candidates if name in pool.columns), None)
    if center_column is None or manager_column is None:
        return {}, []

    center_series = pd.to_numeric(ensure_series(pool[center_column]), errors="coerce").fillna(-1)
    center_series = center_series.astype(int)
    manager_series = ensure_series(pool[manager_column]).astype("string").str.strip()

    result: dict[int, pd.Index] = {}
    missing_centers: list[int] = []

    for center_value, names in manager_map.items():
        normalized_names = [str(name).strip() for name in names if str(name).strip()]
        if not normalized_names:
            continue
        mask = center_series.eq(int(center_value)) & manager_series.isin(normalized_names)
        if mask.any():
            result[int(center_value)] = pool.index[mask]
        else:
            missing_centers.append(int(center_value))
            manager_list = ", ".join(str(name) for name in normalized_names)
            warnings.warn(
                (
                    f"هیچ منتوری با نام‌های {manager_list or 'نامشخص'} برای مرکز "
                    f"{center_value} یافت نشد. دانش‌آموزان این مرکز بدون محدودیت مدیر "
                    "تخصیص خواهند یافت."
                ),
                UserWarning,
                stacklevel=2,
            )

    if missing_centers and (
        policy.center_management.strict_manager_validation or strict_validation
    ):
        raise ValueError(f"مدیران مورد نیاز برای مراکز {missing_centers} در استخر یافت نشدند")

    return result, missing_centers


def _normalize_rule_details(payload: object) -> Mapping[str, object] | None:
    """نرمال‌سازی جزئیات rule برای گزارش."""
    if isinstance(payload, Mapping):
        return dict(payload)
    return None


def _derive_rule_reason(
    trace: Sequence[TraceStageRecord],
) -> tuple[str, str, Mapping[str, object] | None]:
    """تعیین کد/متن دلیل بر اساس اولین مرحلهٔ رد."""
    fallback = build_reason(ReasonCode.OK)
    if not trace:
        return fallback.code, fallback.message_fa, None
    for record in trace:
        extras = record.get("extras") or {}
        code = extras.get("rule_reason_code")
        message = extras.get("rule_reason_text")
        details = _normalize_rule_details(extras.get("rule_details"))
        after = int(record.get("total_after", 0))
        if code and (not record.get("matched") or after == 0):
            return str(code), str(message or fallback.message_fa), details
    tail_extras = trace[-1].get("extras") or {}
    code = tail_extras.get("rule_reason_code")
    message = tail_extras.get("rule_reason_text")
    details = _normalize_rule_details(tail_extras.get("rule_details"))
    if code:
        return (str(code), str(message or fallback.message_fa), details)
    return fallback.code, fallback.message_fa, None


def _display_expected_value(value: object) -> str:
    """تبدیل مقدار مورد انتظار به متن قابل‌گزارش."""
    if value is None:
        return "نامشخص"
    try:
        if pd.isna(value):
            return "نامشخص"
    except Exception:
        pass
    text = str(value).strip()
    return text or "نامشخص"


def _format_alert_message(stage: str, record: TraceStageRecord | None) -> str:
    """ساخت پیام فارسی برای هشدار حذف کاندید در یک مرحله."""
    label = _STAGE_LABEL_FA.get(stage, stage)
    expected_value = record.get("expected_value") if record else None
    if stage == "capacity_gate":
        column = record.get("column") if record else None
        column_text = str(column or "remaining_capacity")
        return f"ظرفیت فعال در ستون {column_text} صفر است؛ هیچ منتوری باقی نماند."
    value_text = _display_expected_value(expected_value)
    return f"فیلتر {label} با مقدار {value_text} هیچ کاندیدی باقی نگذاشت."


def _derive_failure_alerts(
    stage_candidate_counts: Mapping[TraceStageName, int],
    trace: Sequence[TraceStageRecord],
    *,
    error_type: str,
) -> list[AllocationAlertRecord]:
    """استخراج هشدارهای ساخت‌یافته براساس stage و trace."""
    if not stage_candidate_counts:
        return []
    if error_type == "ELIGIBILITY_NO_MATCH":
        stage_sequence: tuple[TraceStageName, ...] = _JOIN_STAGE_FAILURE_ORDER
    elif error_type == "CAPACITY_FULL":
        stage_sequence = ("capacity_gate",)
    else:
        return []
    failing_stage = next(
        (stage for stage in stage_sequence if stage_candidate_counts.get(stage) == 0),
        None,
    )
    if failing_stage is None:
        return []
    record = next((item for item in trace if item.get("stage") == failing_stage), None)
    message = _format_alert_message(failing_stage, record)
    context: dict[str, Any] = {}
    if record is not None:
        context = {
            "column": record.get("column"),
            "expected_value": record.get("expected_value"),
            "total_before": record.get("total_before"),
            "total_after": record.get("total_after"),
        }
        extras = record.get("extras") or {}
        if extras:
            context["extras"] = dict(extras)
    alert: AllocationAlertRecord = {
        "code": str(error_type),
        "stage": str(failing_stage),
        "message": message,
        "context": context,
    }
    return [alert]


def _append_invalid_center_alert(
    log: AllocationLogRecord,
    student_info: Mapping[str, object] | None,
    fallback_center: int | None,
) -> None:
    """ثبت هشدار ساخت‌یافته برای مقادیر نامعتبر ستون مرکز."""
    if not student_info:
        return
    original_center = student_info.get("original_center")
    student_id = student_info.get("student_id")
    column = student_info.get("center_column", "center")
    duplicate = False
    existing_invalid = log.get("invalid_center_alerts")
    if isinstance(existing_invalid, list):
        for entry in existing_invalid:
            if (
                entry.get("student_id") == student_id
                and entry.get("original_center") == original_center
            ):
                duplicate = True
                break
    if duplicate:
        return

    fallback_text = "بدون محدودیت" if fallback_center is None else str(fallback_center)
    original_text = "" if original_center is None else str(original_center)
    message = f"مرکز نامعتبر '{original_text or 'نامشخص'}' به {fallback_text} تغییر یافت"
    context: dict[str, Any] = {
        "column": column,
        "raw_value": original_center,
        "fallback_center": fallback_center,
    }
    alert: AllocationAlertRecord = {
        "code": "INVALID_CENTER",
        "stage": "center",
        "message": message,
        "context": context,
    }

    phase_trace = log.get("phase_rule_trace")
    if isinstance(phase_trace, list):
        phase_trace.append(
            {
                "stage": "student_alert",
                "student_id": student_id,
                "reason": ReasonCode.INVALID_CENTER_VALUE.value,
                "message": message,
            }
        )

    existing_alerts = log.get("alerts")
    if isinstance(existing_alerts, list):
        existing_alerts.append(alert)
    else:
        log["alerts"] = [alert]

    invalid_entries = log.get("invalid_center_alerts")
    if isinstance(invalid_entries, list):
        invalid_entries.append(
            {
                "student_id": student_id,
                "original_center": original_center,
                "fallback_center": fallback_center,
                "message": message,
            }
        )
    else:
        log["invalid_center_alerts"] = [
            {
                "student_id": student_id,
                "original_center": original_center,
                "fallback_center": fallback_center,
                "message": message,
            }
        ]

    warnings.warn(message, stacklevel=2)


def _emit_alert_progress(
    alerts: Sequence[AllocationAlertRecord],
    alert_progress: ProgressFn | None,
) -> None:
    """ارسال پیام هشدار به progress hook برای مشاهدهٔ لحظه‌ای."""
    if not alerts or alert_progress is None or alert_progress is _noop_progress:
        return
    for alert in alerts:
        stage = str(alert.get("stage") or "join")
        pct = 30 if stage == "capacity_gate" else 5
        context = alert.get("context") or {}
        expected = context.get("expected_value")
        try:
            if expected is not None and pd.isna(expected):
                expected = None
        except Exception:
            pass
        column = context.get("column")
        hints: list[str] = []
        if expected not in (None, ""):
            hints.append(f"مقدار={expected}")
        if column:
            hints.append(f"ستون={column}")
        hint_text = f" ({' | '.join(hints)})" if hints else ""
        message = alert.get("message") or "هشدار"
        alert_progress(pct, f"⚠️ {alert.get('code', 'WARNING')} - {message}{hint_text}")


def _build_log_base(
    student: Mapping[str, object],
    policy: PolicyConfig,
    *,
    join_map: Mapping[str, int] | None = None,
    missing: Sequence[str] | None = None,
) -> AllocationLogRecord:
    """ساخت لاگ پایه با استفاده از نگاشت ازپیش‌محاسبه‌شدهٔ کلیدهای join."""
    if join_map is None or missing is None:
        join_map, missing = _collect_join_key_map(student, policy)
    if missing:
        raise JoinKeyDataMissingError(missing, join_map)
    return _build_log_from_join_map(student, join_map)


def _normalize_students(df: pd.DataFrame, policy: PolicyConfig) -> pd.DataFrame:
    """نرمال‌سازی قاب دانش‌آموز برای ورودی تابع allocate_batch."""
    students = canonicalize_students_frame(df, policy=policy)
    for column in policy.join_keys:
        if column in students.columns:
            students[column] = students[column].astype("Int64")
    return students


def _normalize_pool(df: pd.DataFrame, policy: PolicyConfig) -> pd.DataFrame:
    """تبدیل قاب استخر به نمای canonical بدون پاک‌سازی تهاجمی."""
    return canonicalize_pool_frame(
        df,
        policy=policy,
        sanitize_pool=False,
        pool_source="inspactor",
    )


def _ensure_students_canonical(df: pd.DataFrame, policy: PolicyConfig) -> pd.DataFrame:
    """اعتبارسنجی قاب دانش‌آموز canonical و تضمین ستون‌های حیاتی."""
    students = df.copy(deep=True)
    missing = [column for column in policy.join_keys if column not in students.columns]
    if missing:
        raise ValueError(f"Canonical student frame missing columns: {missing}")
    student_id = students.get("student_id")
    if student_id is not None:
        student_id_series = ensure_series(student_id)
        empty_mask = student_id_series.astype("string").str.strip().eq("")
        if empty_mask.any():
            raise ValueError("Canonical student frame contains empty student_id values")
    for column in policy.join_keys:
        series = pd.to_numeric(students[column], errors="coerce")
        if series.isna().any():
            raise ValueError(f"Canonical student join key '{column}' has invalid values")
    return students


def _ensure_pool_canonical(
    df: pd.DataFrame,
    policy: PolicyConfig,
    capacity_column: str,
) -> pd.DataFrame:
    """اعتبارسنجی قاب استخر canonical و تضمین ستون‌های حیاتی."""
    pool = df.copy(deep=True)
    required = set(policy.join_keys) | {
        "کد کارمندی پشتیبان",
        "mentor_id",
        "remaining_capacity",
        "allocations_new",
        "occupancy_ratio",
    }
    missing = [column for column in required if column not in pool.columns]
    if missing:
        raise ValueError(f"Canonical pool frame missing columns: {missing}")
    numeric_candidates = {
        capacity_column,
        policy.columns.remaining_capacity,
        "remaining_capacity",
    }
    for column in numeric_candidates:
        if column in pool.columns:
            numeric = pd.to_numeric(pool[column], errors="coerce")
            if numeric.isna().any():
                raise ValueError(f"Canonical pool column '{column}' has non-numeric values")
    return pool


def _detect_pool_mismatch(
    *,
    candidate_pool: pd.DataFrame,
    pool_view: pd.DataFrame,
    pool_state_view: pd.DataFrame | None,
) -> bool:
    """بررسی ناسازگاری بین ایندکس استخر کاندید و ظرفیت."""
    state_view = pool_state_view if pool_state_view is not None else pool_view
    candidate_index = pd.Index(candidate_pool.index)
    missing_indexes = candidate_index.difference(state_view.index)
    return bool(missing_indexes.size)


def allocate_student(
    student: Mapping[str, object],
    candidate_pool: pd.DataFrame,
    *,
    policy: PolicyConfig | None = None,
    progress: ProgressFn = _noop_progress,
    capacity_column: str | None = None,
    trace_plan: Sequence[TraceStagePlan] | None = None,
    stage_rules: Mapping[TraceStageLiteral, Rule] | None = None,
    state: Mapping[Hashable, MentorCapacityState] | None = None,
    pool_state_view: pd.DataFrame | None = None,
    alert_progress: ProgressFn | None = None,
) -> AllocationResult:
    """تخصیص تک‌دانش‌آموز با حفظ Trace و لاگ کامل مطابق §5 Technical SSoT."""
    if policy is None:
        policy = load_policy()
    resolved_capacity_column = _resolve_capacity_column(policy, capacity_column)
    if trace_plan is None:
        trace_plan = build_trace_plan(policy, capacity_column=resolved_capacity_column)
    if stage_rules is None:
        stage_rules = default_stage_rule_map()
    if alert_progress is None:
        alert_progress = progress

    student_row = cast(StudentRow, dict(student))

    # پردازش مرکز دانش‌آموز
    center_info = _resolve_student_center_info(student, policy)
    center_fallback = None
    if center_info.is_invalid and center_info.normalized_value is None:
        center_fallback = policy.default_center_for_invalid
    center_alert_payload: dict[str, object] | None = None
    if center_info.is_invalid:
        center_alert_payload = {
            "student_id": student.get("student_id"),
            "original_center": center_info.raw_value,
            "center_column": center_info.column,
        }

    # جمع‌آوری join keys با بهبود برای باگ‌های join
    try:
        join_map, missing_columns = _collect_join_key_map(student, policy)
    except JoinKeyDataInvalidError as exc:
        trace: list[TraceStageRecord] = []
        log = _build_log_from_join_map(student, exc.join_map)
        log.update(
            {
                "error_type": "DATA_MISSING",
                "detailed_reason": (f"Invalid join key value for '{exc.column}': {exc.value!r}"),
                "suggested_actions": [
                    "نرمال‌سازی ستون‌های join به عدد صحیح",
                    "بازبینی StudentReport",
                ],
                "candidate_count": 0,
                "stage_candidate_counts": _canonical_stage_counts({}),
            }
        )
        return AllocationResult(None, trace, log)

    if pool_state_view is not None:
        pool_state_view = pool_state_view.reindex(candidate_pool.index)

    progress(5, "prefilter")

    stage_candidate_counts: dict[TraceStageName, int] = {
        stage: 0 for stage in CANONICAL_TRACE_ORDER
    }

    def _record_stage(stage: str, count: int) -> None:
        """ثبت شمارنده مراحل برای Trace."""
        stage_name = ensure_trace_stage_name(stage)
        stage_candidate_counts[stage_name] = int(count)

    # اعمال فیلترهای join
    eligible = apply_join_filters(
        candidate_pool,
        student,
        policy=policy,
        student_join_map=join_map,
        tracker=_record_stage,
    )

    # بهبود برای OBS_JOIN_01 - همیشه جمع‌آوری mismatches
    eligible, join_mismatch_details = _filter_candidates_by_join_map(
        eligible,
        join_map=join_map,
        policy=policy,
    )
    _, prefilter_mismatches = _filter_candidates_by_join_map(
        candidate_pool,
        join_map=join_map,
        policy=policy,
    )
    join_mismatch_details = _merge_join_mismatches(join_mismatch_details, prefilter_mismatches)
    stage_candidate_counts = _canonical_stage_counts(stage_candidate_counts)

    trace = build_allocation_trace(
        student_row,
        candidate_pool,
        policy=policy,
        stage_plan=trace_plan,
        capacity_column=resolved_capacity_column,
        stage_rules=stage_rules,
    )
    rule_reason_code, rule_reason_text, rule_details = _derive_rule_reason(trace)

    try:
        log = _build_log_base(
            student,
            policy,
            join_map=join_map,
            missing=missing_columns,
        )
    except JoinKeyDataMissingError as exc:
        log = _build_log_from_join_map(student, exc.join_map)
        log.update(
            {
                "rule_reason_code": rule_reason_code,
                "rule_reason_text": rule_reason_text,
                "rule_reason_details": rule_details,
            }
        )
        log["candidate_count"] = int(eligible.shape[0])
        log["stage_candidate_counts"] = _canonical_stage_counts(stage_candidate_counts)
        missing_text = ", ".join(exc.missing_columns)
        log.update(
            {
                "error_type": "DATA_MISSING",
                "detailed_reason": f"Missing student join key data: {missing_text}",
                "suggested_actions": [
                    "تکمیل دادهٔ دانش‌آموز",
                    "بازبینی StudentReport",
                ],
            }
        )
        if center_alert_payload is not None and not center_alert_payload.get("student_id"):
            center_alert_payload["student_id"] = log.get("student_id")
        _append_invalid_center_alert(log, center_alert_payload, center_fallback)
        return AllocationResult(None, trace, log)

    pool_mismatch_detected = _detect_pool_mismatch(
        candidate_pool=eligible,
        pool_view=candidate_pool,
        pool_state_view=pool_state_view,
    )

    def _fail_allocation(
        detailed_reason: str,
        *,
        error_type: AllocationErrorLiteral = "INTERNAL_ERROR",
        suggested_actions: Sequence[str] | None = None,
        extra_updates: AllocationLogRecord | Mapping[str, object] | None = None,
    ) -> AllocationResult:
        """هلپر برای شکست تخصیص با ثبت لاگ مناسب."""
        payload: AllocationLogRecord = {
            "detailed_reason": detailed_reason,
            "error_type": error_type,
            "suggested_actions": list(suggested_actions or []),
        }
        alerts = _derive_failure_alerts(
            stage_candidate_counts,
            trace,
            error_type=error_type,
        )
        if alerts:
            existing = log.get("alerts")
            if isinstance(existing, list):
                existing.extend(alerts)
            else:
                log["alerts"] = list(alerts)
            _emit_alert_progress(alerts, alert_progress)
        if extra_updates:
            payload.update(cast(AllocationLogRecord, dict(extra_updates)))
        log.update(payload)
        return AllocationResult(None, trace, log)

    log["candidate_count"] = int(eligible.shape[0])
    log["stage_candidate_counts"] = _canonical_stage_counts(stage_candidate_counts)
    log["rule_reason_code"] = rule_reason_code
    log["rule_reason_text"] = rule_reason_text
    log["rule_reason_details"] = rule_details

    if center_alert_payload is not None and not center_alert_payload.get("student_id"):
        center_alert_payload["student_id"] = log.get("student_id")
    _append_invalid_center_alert(log, center_alert_payload, center_fallback)

    # بهبود برای OBS_JOIN_01 - همیشه ثبت mismatches
    if join_mismatch_details:
        log["join_key_mismatches"] = list(join_mismatch_details)

    if eligible.empty:
        if not join_mismatch_details:
            _, join_mismatch_details = _filter_candidates_by_join_map(
                candidate_pool,
                join_map=join_map,
                policy=policy,
            )
        extra_updates = (
            {"join_key_mismatches": join_mismatch_details} if join_mismatch_details else None
        )
        return _fail_allocation(
            "No candidates matched join keys",
            error_type="ELIGIBILITY_NO_MATCH",
            suggested_actions=["بازبینی دادهٔ ورودی", "تطبیق join keys"],
            extra_updates=extra_updates,
        )

    progress(30, "capacity")

    state_frame = pool_state_view if pool_state_view is not None else candidate_pool
    state_view_en = dedupe_columns(canonicalize_headers(state_frame, header_mode="en"))

    capacity_candidates: list[str] = []
    if "remaining_capacity" in state_view_en.columns:
        capacity_candidates.append("remaining_capacity")
    capacity_candidates.append(resolved_capacity_column)
    derived_name = canonicalize_headers(
        pd.DataFrame(columns=[resolved_capacity_column]),
        header_mode="en",
    ).columns[0]
    if derived_name not in capacity_candidates:
        capacity_candidates.append(derived_name)

    capacity_column_name: str | None = None
    for candidate in capacity_candidates:
        if candidate in state_view_en.columns:
            capacity_column_name = candidate
            break
    if capacity_column_name is None:
        raise KeyError(
            f"Capacity column '{resolved_capacity_column}' not found after canonicalization"
        )

    capacity_series = ensure_series(state_view_en.loc[eligible.index, capacity_column_name])
    capacity_numeric = pd.to_numeric(capacity_series, errors="coerce").fillna(0).astype(int)
    capacity_mask = capacity_numeric > 0
    capacity_filtered = eligible.loc[capacity_mask.values]
    stage_candidate_counts["capacity_gate"] = int(capacity_mask.sum())
    stage_candidate_counts = _canonical_stage_counts(stage_candidate_counts)
    log["stage_candidate_counts"] = stage_candidate_counts

    for stage_entry in trace:
        if stage_entry["stage"] != "capacity_gate":
            continue
        total_before_capacity = int(capacity_series.shape[0])
        total_after_capacity = int(capacity_mask.sum())
        stage_entry["total_before"] = total_before_capacity
        stage_entry["total_after"] = total_after_capacity
        stage_entry["matched"] = bool(total_after_capacity)
        extras = dict(stage_entry.get("extras") or {})
        extras["capacity_before"] = total_before_capacity
        extras["capacity_after"] = total_after_capacity
        stage_entry["extras"] = extras
        break

    pool_mismatch_detected = pool_mismatch_detected or _detect_pool_mismatch(
        candidate_pool=capacity_filtered,
        pool_view=candidate_pool,
        pool_state_view=pool_state_view,
    )
    log["pool_mismatch_detected"] = pool_mismatch_detected

    if capacity_filtered.empty:
        error_updates: dict[str, object] = {}
        if join_mismatch_details:
            error_updates["join_key_mismatches"] = join_mismatch_details
        return _fail_allocation(
            "No capacity among matched candidates",
            error_type=_derive_error_type_from_stage_counts(stage_candidate_counts),
            suggested_actions=["بازبینی join keys", "افزایش ظرفیت", "بازنگری محدودیت‌ها"],
            extra_updates=error_updates if error_updates else None,
        )

    progress(60, "ranking")

    ranking_input = capacity_filtered.copy()
    active_state = (
        _stringify_mentor_state(state)
        if state is not None
        else _stringify_mentor_state(
            build_mentor_state(state_view_en, capacity_column=capacity_column_name, policy=policy)
        )
    )
    ranking_state = cast(
        Mapping[Hashable, Mapping[str, int | float | str | None]],
        active_state,
    )

    # ابتدا سیاست رتبه‌بندی رسمی اجرا می‌شود
    ranked = apply_ranking_policy(ranking_input, state=ranking_state, policy=policy)

    fairness_reason = ranked.attrs.get("fairness_reason")
    if fairness_reason is not None:
        fairness_code = getattr(fairness_reason, "code", None)
        fairness_message = getattr(fairness_reason, "message_fa", None)
        log["fairness_reason_code"] = fairness_code
        formatted: str | None
        if fairness_code and fairness_message:
            formatted = f"[{fairness_code}] {fairness_message}"
        else:
            formatted = fairness_message
        log["fairness_reason_text"] = formatted

    if ranked.empty:
        return _fail_allocation(
            "Ranking policy returned no candidates",
            suggested_actions=[
                "بازبینی دادهٔ استخر پشتیبان",
                "بررسی قوانین رتبه‌بندی",
            ],
        )

    if ranked.empty:
        return _fail_allocation(
            "Ranking policy produced empty set after state-based ordering",
            suggested_actions=[
                "بازبینی دادهٔ استخر پشتیبان",
                "بررسی سازگاری state با pool",
            ],
        )

    try:
        chosen_index = ranked.index[0]
        selected_row = capacity_filtered.loc[chosen_index]
    except (IndexError, KeyError):
        return _fail_allocation(
            "Unable to select ranked candidate",
            suggested_actions=[
                "بازبینی منطق رتبه‌بندی",
                "بررسی فیلترهای capacity",
            ],
        )

    chosen_row = ranked.iloc[0].copy()
    ranked_en = canonicalize_headers(
        ranked,
        header_mode=cast(HeaderMode, policy.excel.header_mode_internal),
    )
    if ranked_en.empty:
        return _fail_allocation(
            "Canonicalization returned empty ranked view",
            suggested_actions=[
                "بازبینی canonicalize_headers",
                "هماهنگی schema استخر با Policy",
            ],
        )

    try:
        chosen_en = ranked_en.iloc[0]
    except IndexError:
        return _fail_allocation(
            "Unable to read ranked row after canonicalization",
            suggested_actions=[
                "بازبینی stage رتبه‌بندی",
                "بررسی canonicalize_headers",
            ],
        )

    mentor_identifier = _normalize_mentor_identifier(
        chosen_row.get("mentor_id_en", chosen_en.get("mentor_id"))
    )
    snapshot_entry = _snapshot_state_entry(
        active_state.get(mentor_identifier)
        if active_state and mentor_identifier is not None
        else None
    )
    capacity_before = int(snapshot_entry.get("remaining", 0))
    capacity_after = capacity_before
    occupancy_value = float(chosen_row.get("occupancy_ratio", 0.0))

    join_valid, join_mismatches = validate_selected_mentor_join_keys(
        selected_row,
        student_join_map=join_map,
        policy=policy,
    )
    if not join_valid:
        corruption_updates: dict[str, object] = {
            "join_key_mismatches": list(join_mismatches),
            "validation_stage": "pre_consume",
            "data_corruption_detected": True,
            "chosen_index": int(chosen_index),
        }
        if mentor_identifier is not None:
            corruption_updates["mentor_id"] = mentor_identifier
        mentor_alias_value = selected_row.get("جایگزین | alias") or selected_row.get("alias")
        if mentor_alias_value is not None:
            corruption_updates["mentor_alias"] = mentor_alias_value
        return _fail_allocation(
            "Selected mentor violates join-key constraints (pool conflict)",
            error_type="INTERNAL_ERROR",
            suggested_actions=[
                "بازسازی استخر پشتیبان",
                "بررسی تعارض join keys برای mentor_id",
            ],
            extra_updates=corruption_updates,
        )

    if mentor_identifier is None:
        return _fail_allocation(
            "Mentor identifier missing after normalization",
            error_type="DATA_MISSING",
            suggested_actions=["بازبینی شناسه‌های پشتیبان", "بازسازی دادهٔ استخر"],
        )

    try:
        capacity_before, capacity_after, occupancy_value = consume_capacity(
            cast(dict[Hashable, MentorCapacityState], active_state),
            mentor_identifier,
        )
    except KeyError as exc:
        log.update(
            {
                "allocation_status": "failed",
                "mentor_selected": None,
                "mentor_id": None,
                "error_type": "INTERNAL_ERROR",
                "detailed_reason": str(exc),
                "suggested_actions": [
                    "بازسازی state ظرفیت",
                    "بررسی داده‌های استخر",
                ],
            }
        )
        return AllocationResult(None, trace, log)
    except ValueError as exc:
        error_code = str(exc) or "CAPACITY_UNDERFLOW"
        known_errors: set[AllocationErrorLiteral] = {
            "ELIGIBILITY_NO_MATCH",
            "CAPACITY_FULL",
            "DATA_MISSING",
            "INTERNAL_ERROR",
            "CAPACITY_UNDERFLOW",
        }
        error_type_value: AllocationErrorLiteral = (
            cast(AllocationErrorLiteral, error_code)
            if error_code in known_errors
            else "INTERNAL_ERROR"
        )
        student_label = str(log.get("student_id") or student.get("student_id", ""))
        snapshot_detail = (
            "mentor snapshot: "
            f"remaining={snapshot_entry['remaining']}, "
            f"alloc_new={snapshot_entry['alloc_new']}, "
            f"occupancy_ratio={snapshot_entry['occupancy_ratio']:.4f}"
        )
        log["mentor_state_delta"] = _build_state_delta(snapshot_entry, snapshot_entry)
        log.update(
            {
                "allocation_status": "failed",
                "mentor_selected": None,
                "mentor_id": None,
                "error_type": error_type_value,
                "detailed_reason": (
                    "Mentor capacity underflow detected; "
                    f"student={student_label or 'unknown'}; "
                    f"mentor={mentor_identifier or 'unknown'}; {snapshot_detail}"
                ),
                "suggested_actions": [
                    "بازبینی ظرفیت ورودی",
                    "اجرای مجدد sanitize pool",
                ],
            }
        )
        return AllocationResult(None, trace, log)

    mentor_name = chosen_row.get("پشتیبان", chosen_row.get("mentor_name", ""))
    mentor_id_text = chosen_row.get("کد کارمندی پشتیبان", chosen_en.get("mentor_id", ""))

    mentor_state_after = _snapshot_state_entry(
        active_state.get(mentor_identifier) if active_state else None
    )
    log["mentor_state_delta"] = _build_state_delta(snapshot_entry, mentor_state_after)

    tie_breakers = {
        "stage1": {
            "metric": "remaining_capacity",
            "value": int(mentor_state_after.get("remaining", 0)),
        },
        "stage2": {
            "metric": "natural mentor_id",
            "value": list(chosen_row.get("mentor_sort_key", ())),
        },
    }

    log.update(
        {
            "row_index": int(chosen_index) if chosen_index is not None else 0,
            "allocation_status": "success",
            "mentor_selected": str(mentor_name),
            "mentor_id": mentor_id_text,
            "occupancy_ratio": float(occupancy_value),
            "selection_reason": "policy: max remaining → natural mentor_id",
            "tie_breakers": tie_breakers,
            "capacity_before": int(capacity_before),
            "capacity_after": int(capacity_after),
            "stage_candidate_counts": _canonical_stage_counts(stage_candidate_counts),
            "pool_mismatch_detected": pool_mismatch_detected,
        }
    )

    if join_mismatch_details:
        log["join_key_mismatches"] = list(join_mismatch_details)

    return AllocationResult(selected_row, trace, log)


def allocate_batch(
    students: pd.DataFrame,
    candidate_pool: pd.DataFrame,
    *,
    policy: PolicyConfig | None = None,
    progress: ProgressFn = _noop_progress,
    capacity_column: str | None = None,
    frames_already_canonical: bool = False,
    center_manager_map: Mapping[int, Sequence[str]] | None = None,
    center_priority: Sequence[int] | None = None,
    ui_center_manager_map: Mapping[int, Sequence[str]] | None = None,
    strict_center_validation: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """تخصیص دسته‌ای دانش‌آموزان و بازگشت خروجی‌های چهارتایی مطابق §3 Technical SSoT."""
    if policy is None:
        policy = load_policy()
    resolved_capacity_column = _resolve_capacity_column(policy, capacity_column)

    capacity_internal = canonicalize_headers(
        pd.DataFrame(columns=[resolved_capacity_column]),
        header_mode=cast(HeaderMode, policy.excel.header_mode_internal),
    ).columns[0]

    def _validate_pool(frame: pd.DataFrame) -> pd.DataFrame:
        """اعتبارسنجی قاب استخر."""
        try:
            return _ensure_pool_canonical(frame, policy, resolved_capacity_column)
        except ValueError as exc:
            if frames_already_canonical:
                raise ValueError("DATA_MISSING") from exc
            raise

    # نرمال‌سازی ورودی‌ها
    if frames_already_canonical:
        students_norm = _ensure_students_canonical(students, policy)
        pool_norm = _validate_pool(candidate_pool)
    else:
        students_norm = _normalize_students(students, policy)
        pool_norm = _validate_pool(_normalize_pool(candidate_pool, policy))

    # پیکربندی مدیریت مرکز
    final_manager_map, final_priority = resolve_center_manager_config(
        policy=policy,
        ui_managers=cast(Mapping[int | str, object] | None, ui_center_manager_map),
        cli_managers=cast(Mapping[int | str, object] | None, center_manager_map),
        cli_priority=center_priority,
        cli_strict_validation=strict_center_validation,
    )
    config_warnings = validate_center_config(policy, final_manager_map, final_priority)
    for message in config_warnings:
        warnings.warn(message, UserWarning, stacklevel=2)

    # مرتب‌سازی و جداسازی دانش‌آموزان
    sorted_students = _sort_students_by_center_priority(students_norm, policy, final_priority)
    school_students, center_students = _separate_school_students(sorted_students, policy)
    students_norm = pd.concat([school_students, center_students], axis=0)

    # آماده‌سازی استخر
    pool_stats = pool_norm.attrs.get("pool_canonicalization_stats")
    alias_autofill = int(getattr(pool_stats, "alias_autofill", 0) or 0) if pool_stats else 0
    alias_unmatched = int(getattr(pool_stats, "alias_unmatched", 0) or 0) if pool_stats else 0
    extra_columns = [column for column in pool_norm.columns if column not in candidate_pool.columns]

    pool_with_ids = inject_mentor_id(pool_norm, build_mentor_id_map(pool_norm))

    # تضمین ستون‌های مورد نیاز
    if "mentor_sort_key" not in pool_with_ids.columns:
        pool_with_ids["mentor_sort_key"] = pool_with_ids["کد کارمندی پشتیبان"].map(natural_key)
    if "allocations_new" not in pool_with_ids.columns:
        pool_with_ids["allocations_new"] = 0
    if "occupancy_ratio" not in pool_with_ids.columns:
        pool_with_ids["occupancy_ratio"] = 0.0

    # رتبه‌بندی اولیه: فقط بر اساس کلید طبیعی پشتیبان برای پایداری
    if "mentor_sort_key" in pool_with_ids.columns:
        pool_with_ids = pool_with_ids.sort_values(
            by=["mentor_sort_key"],
            ascending=[True],
            kind="stable",
        )

    pool_internal = canonicalize_headers(pool_with_ids, header_mode="en")
    pool_internal = pool_internal.loc[:, ~pool_internal.columns.duplicated(keep="first")]

    # تضمین ستون‌های حیاتی در نمای داخلی
    if "mentor_sort_key" not in pool_internal.columns and (
        "mentor_sort_key" in pool_with_ids.columns
    ):
        pool_internal["mentor_sort_key"] = pool_with_ids["mentor_sort_key"].values
    if capacity_internal not in pool_internal.columns:
        pool_internal[capacity_internal] = 0
    if "allocations_new" not in pool_internal.columns:
        pool_internal["allocations_new"] = 0
    if "occupancy_ratio" not in pool_internal.columns:
        pool_internal["occupancy_ratio"] = 0.0
    if "mentor_id" not in pool_internal.columns:
        raise KeyError("Pool must contain 'mentor_id' column after canonicalization")

    # ساخت state اولیه
    mentor_state = _stringify_mentor_state(
        build_mentor_state(pool_internal, capacity_column=capacity_internal, policy=policy)
    )

    # ساخت ایندکس مدیران مرکز
    center_manager_index, _ = _build_center_manager_index(
        pool_with_ids,
        policy,
        final_manager_map,
        strict_validation=strict_center_validation,
    )
    center_column_name = policy.stage_column("center")

    # داده‌های خروجی
    allocations: list[Mapping[str, object]] = []
    logs: list[AllocationLogRecord] = []
    trace_rows: list[Mapping[str, object]] = []
    trace_outcomes: list[TraceOutcome] = []

    stage_rules = default_stage_rule_map()
    total = max(int(students_norm.shape[0]), 1)
    trace_plan = build_trace_plan(policy, capacity_column=resolved_capacity_column)

    progress(0, "start")
    processed = 0

    def _allocate_group(
        group: pd.DataFrame,
        *,
        enforce_center_manager: bool,
        phase_stage: str,
        rule_engine: RuleEngine,
    ) -> None:
        """هلپر برای تخصیص گروهی از دانش‌آموزان."""
        nonlocal processed
        if group.empty:
            return

        stage_students = _phase_guard_source(group, policy)
        stage_extras = _phase_stage_extras(phase_stage, pool_with_ids, resolved_capacity_column)
        base_phase_trace = rule_engine.run_stage(phase_stage, stage_students, extras=stage_extras)
        is_school_phase = not enforce_center_manager

        for _, student_row in group.iterrows():
            processed += 1
            student_dict = student_row.to_dict()
            progress(int(processed * 100 / total), f"allocating {processed}/{total}")

            student_center, center_is_valid = _extract_and_validate_center(student_dict, policy)
            invalid_center_payload: dict[str, object] | None = None
            if not center_is_valid:
                invalid_center_payload = {
                    "student_id": student_dict.get("student_id", processed),
                    "original_center": student_dict.get(center_column_name),
                    "center_column": center_column_name,
                }

            # بهبود برای BUG_CAP_01 - هماهنگی pool_view و pool_state_view
            pool_view = pool_with_ids
            pool_state_view_local = pool_internal
            if enforce_center_manager and student_center is not None:
                center_key = int(student_center)
                manager_index = center_manager_index.get(center_key)
                if manager_index is not None and len(manager_index) > 0:
                    pool_view = pool_with_ids.loc[manager_index]
                    pool_state_view_local = pool_internal.loc[manager_index]

            result = allocate_student(
                student_dict,
                pool_view,
                policy=policy,
                progress=_noop_progress,
                capacity_column=resolved_capacity_column,
                trace_plan=trace_plan,
                stage_rules=stage_rules,
                state=cast(Mapping[Hashable, MentorCapacityState], mentor_state),
                pool_state_view=pool_state_view_local,
                alert_progress=progress,
            )

            if invalid_center_payload is not None:
                _append_invalid_center_alert(result.log, invalid_center_payload, student_center)

            phase_trace: list[Mapping[str, Any]] = [dict(entry) for entry in base_phase_trace]
            existing_phase_entries = result.log.get("phase_rule_trace")
            if isinstance(existing_phase_entries, list) and existing_phase_entries:
                phase_trace.extend(existing_phase_entries)

            if is_school_phase:
                phase_trace.append(
                    {
                        "stage": "student_allocation",
                        "student_id": student_dict.get("student_id"),
                        "reason": ReasonCode.SCHOOL_STUDENT_PRIORITY.value,
                        "message": _phase_reason_message(ReasonCode.SCHOOL_STUDENT_PRIORITY),
                    }
                )
            else:
                mentor_payload = (
                    result.mentor_row.to_dict() if result.mentor_row is not None else None
                )
                phase_reason = rule_engine.evaluate_pair(student_dict, mentor_payload)
                if phase_reason is not None:
                    stage_name = "student_allocation"
                    if phase_reason in (
                        ReasonCode.CENTER_MISMATCH,
                        ReasonCode.NO_MANAGER_FOR_CENTER,
                    ):
                        stage_name = "student_rejection"
                    elif phase_reason is ReasonCode.INVALID_CENTER_VALUE:
                        stage_name = "student_alert"
                    phase_trace.append(
                        {
                            "stage": stage_name,
                            "student_id": student_dict.get("student_id"),
                            "reason": phase_reason.value,
                            "message": _phase_reason_message(phase_reason),
                        }
                    )

            result.log["phase_rule_trace"] = phase_trace
            logs.append(result.log)

            for stage in result.trace:
                trace_rows.append({"student_id": result.log["student_id"], **stage})

            outcome = summarize_trace_outcome(student_dict, result.trace, result.log, policy=policy)
            trace_outcomes.append(outcome)
            result.log["trace_final_status"] = outcome.final_status
            result.log["trace_failure_stage"] = outcome.failure_stage
            result.log["trace_final_reason"] = outcome.final_reason
            result.log["trace_stage_flags"] = dict(outcome.stage_flags)

            # بهبود برای BUG_OUT_01 - تضمین خروجی بر اساس allocation_status
            if result.mentor_row is not None and result.log.get("allocation_status") == "success":
                chosen_index = result.mentor_row.name
                mentor_identifier = _resolve_mentor_identifier(result, policy=policy)
                resolved_identifier, state_entry = _resolve_mentor_state_entry(
                    mentor_state,
                    mentor_identifier,
                )
                if state_entry is None:
                    raise KeyError(
                        f"Mentor '{mentor_identifier}' missing from state after allocation"
                    )

                # به‌روزرسانی state و pool
                pool_internal.loc[chosen_index, capacity_internal] = state_entry["remaining"]
                if (
                    capacity_internal != "remaining_capacity"
                    and "remaining_capacity" in pool_internal.columns
                ):
                    pool_internal.loc[chosen_index, "remaining_capacity"] = state_entry["remaining"]
                pool_internal.loc[chosen_index, "allocations_new"] = state_entry["alloc_new"]
                pool_internal.loc[chosen_index, "occupancy_ratio"] = state_entry.get(
                    "occupancy_ratio", 0.0
                )

                pool_with_ids.loc[chosen_index, resolved_capacity_column] = state_entry["remaining"]
                if (
                    resolved_capacity_column != "remaining_capacity"
                    and "remaining_capacity" in pool_with_ids.columns
                ):
                    pool_with_ids.loc[chosen_index, "remaining_capacity"] = state_entry["remaining"]
                pool_with_ids.loc[chosen_index, "allocations_new"] = state_entry["alloc_new"]
                pool_with_ids.loc[chosen_index, "occupancy_ratio"] = state_entry.get(
                    "occupancy_ratio", 0.0
                )

                mentor_id_display = result.log.get("mentor_id")
                if mentor_id_display is None:
                    mentor_id_display = resolved_identifier

                student_national_code = _extract_student_national_code(student_dict)
                mentor_alias_code = _extract_mentor_alias_code(result.mentor_row)

                allocations.append(
                    {
                        "student_id": student_dict.get("student_id", ""),
                        "student_national_code": student_national_code,
                        "mentor": result.mentor_row.get("پشتیبان", ""),
                        "mentor_id": "" if mentor_id_display is None else str(mentor_id_display),
                        "mentor_alias_code": mentor_alias_code,
                    }
                )

    # تخصیص فازهای مدرسه‌ای و مرکزی
    school_rules, center_rules = _build_phase_rule_engines(policy)
    _allocate_group(
        school_students,
        enforce_center_manager=False,
        phase_stage="school_phase_start",
        rule_engine=school_rules,
    )
    _allocate_group(
        center_students,
        enforce_center_manager=True,
        phase_stage="center_phase_start",
        rule_engine=center_rules,
    )

    # ثبت آمار alias
    for log in logs:
        log["alias_autofill"] = alias_autofill
        log["alias_unmatched"] = alias_unmatched

    progress(100, "done")

    # ساخت خروجی‌های نهایی
    allocations_df = pd.DataFrame(allocations, columns=_ALLOCATION_OUTPUT_COLUMNS)
    logs_df = pd.DataFrame(logs)
    trace_df = pd.DataFrame(trace_rows)

    # پردازش نتایج Trace
    if trace_outcomes:
        outcome_records: list[dict[str, object]] = []
        for outcome in trace_outcomes:
            record: dict[str, object] = {
                "student_id": outcome.student_id,
                "final_status": outcome.final_status,
                "failure_stage": outcome.failure_stage,
                "final_reason": outcome.final_reason,
            }
            record.update({f"passed_{k}": v for k, v in outcome.stage_flags.items()})
            record.update(outcome.metadata)
            outcome_records.append(record)
        trace_summary_df = pd.DataFrame(outcome_records)
        if "student_id" in trace_summary_df.columns:
            trace_summary_df = trace_summary_df.drop_duplicates(subset=["student_id"], keep="last")
            if "student_id" in students.columns:
                ordered_ids = students["student_id"].tolist()
                trace_summary_df = (
                    trace_summary_df.set_index("student_id").reindex(ordered_ids).reset_index()
                )
        if "student_id" in trace_summary_df.columns and "student_id" in students.columns:
            student_indexed = students.set_index("student_id", drop=False)
            for column in (
                "student_national_code",
                "student_registration_status",
                "student_educational_status",
                "student_first_name",
                "student_last_name",
            ):
                if column in student_indexed.columns and column not in trace_summary_df.columns:
                    trace_summary_df[column] = trace_summary_df["student_id"].map(
                        student_indexed[column]
                    )

        trace_summary_df = attach_allocation_channel(trace_summary_df, students_norm, policy=policy)
        trace_df.attrs["summary_df"] = trace_summary_df
        trace_df.attrs["unallocated_summary"] = build_unallocated_summary(
            trace_summary_df,
            policy=policy,
        )
        trace_df.attrs["final_status_counts"] = trace_summary_df["final_status"].value_counts()
        trace_df.attrs["policy_violations"] = find_allocation_policy_violations(
            trace_summary_df,
            pool_with_ids,
            policy=policy,
        )

    # آماده‌سازی خروجی استخر
    pool_output = pool_with_ids.copy()
    original_columns = list(candidate_pool.columns)
    desired_columns = original_columns + [
        column for column in extra_columns if column not in original_columns
    ]
    for column in desired_columns:
        if column not in pool_output.columns:
            pool_output[column] = pd.NA
    pool_output = pool_output.loc[:, desired_columns]

    # حفظ انواع داده‌ای اصلی
    for column in original_columns:
        if column in candidate_pool.columns:
            try:
                pool_output[column] = pool_output[column].astype(candidate_pool[column].dtype)
            except (TypeError, ValueError):
                continue

    # اعتبارسنجی نهایی ظرفیت
    for entry in mentor_state.values():
        if entry["remaining"] < 0:
            raise ValueError("Negative remaining capacity detected after allocation")

    internal_remaining = pd.to_numeric(
        ensure_series(pool_internal[capacity_internal]),
        errors="coerce",
    ).fillna(0)
    if (internal_remaining < 0).any():
        raise ValueError("Pool capacity column contains negative values after allocation")

    return allocations_df, pool_output, logs_df, trace_df


def build_selection_reason_rows(
    allocations: pd.DataFrame,
    students: pd.DataFrame,
    mentors: pd.DataFrame,
    *,
    policy: PolicyConfig,
    logs: pd.DataFrame | None = None,
    trace: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """واسطهٔ سازگار برای ساخت شیت دلایل انتخاب پشتیبان."""
    summary_df = None
    if trace is not None:
        summary_attr = getattr(trace, "attrs", {}) or {}
        maybe_summary = summary_attr.get("summary_df")
        if isinstance(maybe_summary, pd.DataFrame) and not maybe_summary.empty:
            summary_df = maybe_summary

    students_enriched = students
    if summary_df is not None and "student_id" in summary_df.columns:
        students_enriched = canonicalize_headers(students, header_mode="en").copy()
        summary_en = canonicalize_headers(summary_df, header_mode="en")
        summary_en = summary_en.drop_duplicates("student_id", keep="first")
        if "student_id" in students_enriched.columns:
            students_enriched = students_enriched.set_index("student_id", drop=False)
            summary_indexed = summary_en.set_index("student_id", drop=False)
            for column in (
                "student_national_code",
                "student_registration_status",
                "student_educational_status",
                "student_first_name",
                "student_last_name",
            ):
                if column in summary_indexed.columns:
                    aligned = summary_indexed[column].reindex(students_enriched.index)
                    base = (
                        students_enriched[column]
                        if column in students_enriched.columns
                        else pd.Series(pd.NA, index=students_enriched.index)
                    )
                    students_enriched[column] = base.where(base.notna(), aligned)
            students_enriched = students_enriched.reset_index(drop=True)
        students_enriched = canonicalize_headers(
            students_enriched,
            header_mode=cast(HeaderMode, policy.excel.header_mode_internal),
        )

    return _build_selection_reason_rows(
        allocations,
        students_enriched,
        mentors,
        policy=policy,
        logs=logs,
        trace=trace,
    )
