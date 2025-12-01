#!/usr/bin/env python3
"""
build_matrix.py — Eligibility Matrix Builder (SSoT v1.0.2, script v1.0.4)

Summary
-------
- Normal mentors: build graduation_status per Policy v1.0.3
  - Dual-status groups `{1, 3, 5, 7, 8, 9, 11, 12, 14, 17, 18}` → {1, 0}
  - Student-only groups (22 codes) → {1}
- School mentors: build ONLY student=1
- Everything else as per SSoT v1.0.2 (capacity gate, crosswalk+synonyms,
  finance 0/1/3, center mapping, atomic writes)
- Patch: When school code is empty, set "کد مدرسه" to numeric 0 in output rows.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from functools import lru_cache
from itertools import product
from logging import getLogger
from typing import Any, Final, Literal, TypeVar

import numpy as np
import pandas as pd

from app.core.allocation.mentor_pool import apply_mentor_pool_governance
from app.core.canonical_frames import (
    POOL_DUPLICATE_SUMMARY_ATTR,
    POOL_JOIN_KEY_DUPLICATES_ATTR,
    canonicalize_pool_frame,
)
from app.core.common.column_normalizer import (
    ColumnNormalizationReport,
    normalize_input_columns,
)
from app.core.common.columns import (
    Source as ColumnSource,
    coerce_semantics,
    ensure_required_columns,
    ensure_series,
    resolve_aliases,
)
from app.core.common.domain import (
    BuildConfig,
    MentorType,
    StudentBindingKind,
    _num_to_int_safe,
    center_from_manager as domain_center_from_manager,
    classify_mentor_mode,
    classify_student_binding,
    compute_alias,
    finance_cross,
    school_code_norm,
)
from app.core.common.normalization import normalize_header, resolve_group_code
from app.core.inspactor_schema_helper import (
    InspactorDefaultConfig,
    missing_inspactor_columns,
    missing_inspactor_diagnostics,
    schema_error_message,
    with_default_inspactor_columns,
)
from app.core.matrix.coverage import (
    CoveragePolicyConfig,
    compute_coverage_metrics,
)
from app.core.policy_loader import (
    MentorSchoolBindingPolicy,
    PolicyConfig,
)
from app.core.qa.coverage_validation import build_coverage_validation_fields

# =============================================================================
# CONSTANTS
# =============================================================================
__version__ = "1.0.4"  # bumped
LOGGER = getLogger(__name__)
# Column headers (Persian per SSoT)
CAPACITY_CURRENT_COL = "تعداد داوطلبان تحت پوشش"
CAPACITY_SPECIAL_COL = "تعداد تحت پوشش خاص"
COL_MENTOR_NAME = "نام پشتیبان"
COL_MANAGER_NAME = "نام مدیر"
COL_MENTOR_ID = "کد کارمندی پشتیبان"  # mandatory; only trusted employee code
COL_MENTOR_ROWID = "ردیف پشتیبان"
COL_GROUP = "گروه آزمایشی"
COL_SCHOOL1 = "نام مدرسه 1"
COL_SCHOOL2 = "نام مدرسه 2"
COL_SCHOOL3 = "نام مدرسه 3"
COL_SCHOOL4 = "نام مدرسه 4"
COL_SCHOOL_CODE = "کد مدرسه"
COL_SCHOOL_COUNT = "تعداد مدارس تحت پوشش"
COL_POSTAL = "کدپستی"
COL_CAN_ALLOC = "امکان جذب دانش آموز"
COL_GENDER = "جنسیت"
COL_STATUS_A = "وضعیت تحصیلی"
COL_STATUS_B = "نوع دانش آموز"
# Optional
COL_GROUP_INCLUDED = "شامل گروه های آزمایشی"

REQUIRED_INSPACTOR_COLUMNS = {
    COL_MENTOR_NAME,
    COL_MANAGER_NAME,
    COL_MENTOR_ID,
    COL_POSTAL,
    COL_SCHOOL_COUNT,
    CAPACITY_CURRENT_COL,
    CAPACITY_SPECIAL_COL,
    COL_GROUP,
}

DERIVED_INSPACTOR_COLUMNS = frozenset(
    {
        COL_SCHOOL_COUNT,
        COL_POSTAL,
        CAPACITY_CURRENT_COL,
        CAPACITY_SPECIAL_COL,
    }
)

REQUIRED_SCHOOL_COLUMNS = {COL_SCHOOL_CODE}

# Regex / normalization
_RE_BIDI = re.compile("[\u200c-\u200f\u202a-\u202e]")
_RE_NONWORD = re.compile(r"[^\w\u0600-\u06FF0-9\s]+", flags=re.UNICODE)
_RE_WHITESPACE = re.compile(r"\s+")
_TRANS_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_RE_SPLIT_ITEMS = re.compile(r"[,\u060C]\s*")
_RE_RANGE = re.compile(r"^\s*(\d+)\s*[:\-–]\s*(\d+)\s*$")

# Built-in synonyms (keys normalized later)
BUILTIN_SYNONYMS = {
    "دهم علوم انسانی": "دهم انسانی",
    "یازدهم شبکه و نرم‌افزار رایانه": "یازدهم شبکه و نرم افزار رایانه",
    "کل متوسطه 1": "__BUCKET__متوسطه اول",
    "کل متوسطه 2": "__BUCKET__متوسطه دوم",
    "کل دبستان": "__BUCKET__دبستان",
    "کل هنرستان": "__BUCKET__هنرستان",
    "کل کنکوری": "__BUCKET__کنکوری",
    "کنکوریها": "__BUCKET__کنکوری",
}

# Policy v1.0.3: only these 11 groups support both student (1) and graduate (0).
DUAL_STATUS_GROUPS: Final[frozenset[int]] = frozenset({1, 3, 5, 7, 8, 9, 11, 12, 14, 17, 18})


def allowed_statuses_for_group(group_code: int, *, is_school_branch: bool) -> tuple[int, ...]:
    """Return graduation_status domain for the given group and mentor branch.

    School-branch mentors are student-only. Normal mentors may expose both
    statuses only for the Policy-approved dual-status groups; all other groups
    are constrained to the student status (1).
    """

    if is_school_branch:
        return (1,)
    if group_code in DUAL_STATUS_GROUPS:
        return (1, 0)
    return (1,)


# =============================================================================
# PROGRESS API
# =============================================================================
ProgressFn = Callable[[int, str], None]

MatrixMode = Literal["report", "inspactor", "school", "matrix"]
MATRIX_MODE: MatrixMode = "matrix"


def noop_progress(_: int, __: str) -> None:
    """تابع پیش‌فرض پیشرفت که هیچ کاری انجام نمی‌دهد."""


def assert_inspactor_schema(df: pd.DataFrame, policy: PolicyConfig) -> pd.DataFrame:
    """اعتبارسنجی اسکیمای گزارش Inspactor قبل از کاننولیزه‌کردن.

    مثال ساده::

        >>> import pandas as pd
        >>> from app.core.policy_loader import load_policy
        >>> df = pd.DataFrame({COL_MENTOR_NAME: ["الف"], COL_MANAGER_NAME: ["ب"]})
        >>> assert_inspactor_schema(df, load_policy())  # doctest: +SKIP

    Args:
        df: دیتافریم خام گزارش Inspactor.
        policy: پیکربندی سیاست فعال برای پیام خطا.

    Returns:
        دیتافریمی با ستون‌های هم‌نام‌شده و تایپ‌شده.

    Raises:
        KeyError: اگر هر یک از ستون‌های اجباری مفقود باشند.
    """

    context: ColumnSource = "inspactor"
    normalized = resolve_aliases(df, context)
    coerced = coerce_semantics(normalized, context)
    default_cfg = InspactorDefaultConfig(
        school_code_columns=(
            COL_SCHOOL_CODE,
            "کد مدرسه 1",
            "کد مدرسه 2",
            "کد مدرسه 3",
            "کد مدرسه 4",
        ),
        school_count_column=COL_SCHOOL_COUNT,
        derived_factories={
            COL_POSTAL: lambda frame: pd.Series(
                [pd.NA] * len(frame), index=frame.index, dtype="string"
            ),
            CAPACITY_CURRENT_COL: lambda frame: pd.Series(
                [0] * len(frame), index=frame.index, dtype="Int64"
            ),
            CAPACITY_SPECIAL_COL: lambda frame: pd.Series(
                [0] * len(frame), index=frame.index, dtype="Int64"
            ),
        },
    )
    prepared = with_default_inspactor_columns(
        coerced,
        default_cfg,
    )

    def _raise_missing_columns_error(
        frame: pd.DataFrame,
        missing: list[str],
        policy_cfg: PolicyConfig,
        exc: Exception | None = None,
    ) -> None:
        diagnostics = missing_inspactor_diagnostics(frame, missing)
        message = schema_error_message(missing, policy_cfg) + diagnostics
        raise KeyError(message) from exc

    try:
        ensured = ensure_required_columns(prepared, REQUIRED_INSPACTOR_COLUMNS, context)
    except ValueError as exc:
        missing = missing_inspactor_columns(prepared, REQUIRED_INSPACTOR_COLUMNS)
        _raise_missing_columns_error(prepared, missing, policy, exc=exc)
    missing_after = missing_inspactor_columns(ensured, REQUIRED_INSPACTOR_COLUMNS)
    if missing_after:
        _raise_missing_columns_error(ensured, missing_after, policy)
    return ensured


# =============================================================================
# ENUMS
# =============================================================================
class Gender(IntEnum):
    FEMALE = 0
    MALE = auto()


class Status(IntEnum):
    GRADUATE = 0
    STUDENT = auto()


class Center(IntEnum):
    MARKAZ = 0
    GOLESTAN = auto()
    SADRA = auto()


class Finance(IntEnum):
    NORMAL = 0
    BONYAD = auto()
    HEKMAT = 3  # non-sequential on purpose


def _duplicate_summary_payload(
    summary: Mapping[str, object] | None,
) -> tuple[int, list[Mapping[str, object]]]:
    if not isinstance(summary, Mapping):
        return 0, []
    total = safe_int_value(summary.get("total", 0), default=0)
    sample_raw = summary.get("sample")
    rows: list[Mapping[str, object]] = []
    if isinstance(sample_raw, Sequence) and not isinstance(sample_raw, (str, bytes)):
        for item in sample_raw:
            if isinstance(item, Mapping):
                rows.append(item)
    return max(total, 0), rows


def _format_duplicate_warning_message(
    record: Mapping[str, object], join_keys: Sequence[str], mentor_column: str
) -> str:
    mentor_value = record.get(mentor_column) or record.get("mentor_id") or "?"
    group_size = record.get("duplicate_group_size")
    group_text = f"size={group_size}" if group_size not in (None, "") else "size=NA"
    join_parts = [f"{key}={record.get(key)}" for key in join_keys]
    return f"mentor={mentor_value} {group_text} :: {', '.join(join_parts)}"


def _build_duplicate_warning_rows(
    summary: Mapping[str, object] | None,
    *,
    join_keys: Sequence[str],
    mentor_column: str,
) -> list[dict[str, object]]:
    total, sample_rows = _duplicate_summary_payload(summary)
    if total <= 0:
        return []
    warnings: list[dict[str, object]] = [
        {
            "warning_type": "join_key_duplicate_summary",
            "warning_message": (
                f"{total} join-key duplicate rows detected; "
                f"showing {min(len(sample_rows), total)} samples"
            ),
            "warning_payload": json.dumps({"total": total}, ensure_ascii=False),
        }
    ]
    for record in sample_rows:
        warnings.append(
            {
                "warning_type": "join_key_duplicate",
                "warning_message": _format_duplicate_warning_message(
                    record, join_keys, mentor_column
                ),
                "warning_payload": json.dumps(record, ensure_ascii=False),
            }
        )
    return warnings


def _format_duplicate_progress_preview(
    summary: Mapping[str, object] | None,
    *,
    join_keys: Sequence[str],
    mentor_column: str,
) -> str:
    total, sample_rows = _duplicate_summary_payload(summary)
    if total <= 0:
        return ""
    if sample_rows:
        detail = _format_duplicate_warning_message(sample_rows[0], join_keys, mentor_column)
        return f"total={total}; sample={detail}; sheet=pool_join_key_duplicates"
    return "".join(
        [
            f"total={total}; sample=NA; sheet=pool_join_key_duplicates",
        ]
    )


# =============================================================================
# NORMALIZATION
# =============================================================================
@lru_cache(maxsize=1024)
def normalize_fa(text: Any) -> str:
    if text is None or (isinstance(text, float) and math.isnan(text)):
        return ""
    s = str(text).replace("ي", "ی").replace("ك", "ک")
    s = "".join(ch for ch in unicodedata.normalize("NFKD", s) if not unicodedata.combining(ch))
    s = _RE_BIDI.sub("", s)
    s = _RE_NONWORD.sub(" ", s)
    s = s.translate(_TRANS_PERSIAN_DIGITS)
    return _RE_WHITESPACE.sub(" ", s).strip().lower()


_ZERO_WIDTH_CHARS = (
    "\ufeff",
    "\u200b",
    "\u200c",
    "\u200d",
    "\u200e",
    "\u200f",
    "\u202a",
    "\u202b",
    "\u202c",
    "\u202d",
    "\u202e",
    "\u2060",
)
_THOUSAND_SEPARATORS = {",", "\u066c", "\u060c", " ", "\u00a0", "\u202f", "_"}
_RE_THOUSAND_GROUP = re.compile(r"^[+-]?\d{1,3}(,\d{3})*(\.\d+)?$")
_DECIMAL_SEPARATORS = {ord("\u066b"): ".", ord("\u06d4"): "."}
_DIGIT_TRANSLATIONS = {
    **{ord("۰") + i: str(i) for i in range(10)},
    **{ord("٠") + i: str(i) for i in range(10)},
}
_HYPHEN_TRANSLATIONS = {
    ord("−"): "-",
    ord("‐"): "-",
    ord("‑"): "-",
    ord("‒"): "-",
    ord("–"): "-",
    ord("—"): "-",
    ord("―"): "-",
}
_NUMERIC_TRANSLATION_TABLE = {
    **_DIGIT_TRANSLATIONS,
    **_HYPHEN_TRANSLATIONS,
    **_DECIMAL_SEPARATORS,
    **{ord(ch): None for ch in _ZERO_WIDTH_CHARS},
    **{ord(ch): None for ch in _THOUSAND_SEPARATORS},
}

_DefaultT = TypeVar("_DefaultT")


def to_ascii_numeric(value: str) -> str:
    """نرمال‌سازی اعداد به معادل ASCII با حذف جداکننده‌ها و علائم اضافی."""

    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value))
    translated = normalized.translate(_NUMERIC_TRANSLATION_TABLE)
    return translated.strip()


def parse_int_safe(x: Any, default: _DefaultT | None = None) -> int | _DefaultT | None:
    raw = "" if x is None else str(x)
    normalized = unicodedata.normalize("NFKC", raw)
    normalized = normalized.translate(
        {
            **_DIGIT_TRANSLATIONS,
            **_HYPHEN_TRANSLATIONS,
            **_DECIMAL_SEPARATORS,
            **{ord(ch): None for ch in _ZERO_WIDTH_CHARS},
        }
    ).strip()
    if not normalized:
        return default
    if any(ch in _THOUSAND_SEPARATORS for ch in normalized):
        collapsed = normalized.translate({ord(ch): "," for ch in _THOUSAND_SEPARATORS})
        if not _RE_THOUSAND_GROUP.match(collapsed):
            return default
    s = to_ascii_numeric(normalized)
    if not s:
        return default
    sign = 1
    if s[0] in "+-":
        sign = -1 if s[0] == "-" else 1
        s = s[1:]
    if not s or not s.isascii() or not s.isdigit():
        return default
    return sign * int(s)


def _standardize_numeric_text(value: str) -> str:
    """یکسان‌سازی ارقام فارسی، جداکننده‌ها و علائم اعشاری."""

    sanitized = to_ascii_numeric(value)
    if not sanitized:
        return ""
    sanitized = sanitized.replace("٫", ".")
    sanitized = sanitized.replace("٬", "")
    return sanitized


def _parse_int_from_text(text: str) -> int | None:
    """استخراج مقدار صحیح از رشتهٔ استانداردشده در صورت امکان."""

    if not text:
        return None
    parsed = parse_int_safe(text)
    if parsed is not None:
        return parsed
    digits = text[1:] if text and text[0] in "+-" else text
    if "." in digits:
        integer_part, decimal_part = digits.split(".", 1)
        if (
            integer_part
            and integer_part.isdigit()
            and (not decimal_part or set(decimal_part) <= {"0"})
        ):
            sign = -1 if text and text[0] == "-" else 1
            return sign * int(integer_part)
    return None


def _coerce_int_like(value: Any) -> int | None:
    """تبدیل ورودی به int در صورت امکان بدون تبدیل‌های ناخواسته به float."""

    if value is None:
        return None
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        if math.isnan(value):
            return None
        as_int = int(value)
        if value == as_int:
            return as_int
        return None
    text = _standardize_numeric_text(str(value))
    return _parse_int_from_text(text)


def to_numlike_str(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    normalized = _standardize_numeric_text(raw)
    parsed = _parse_int_from_text(normalized)
    return str(parsed) if parsed is not None else normalized


def ensure_list(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for v in values:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        t = str(v).strip()
        if not t or t == "0":
            continue
        t = t.replace("،", ",").replace("|", ",")
        result.extend(p.strip() for p in t.split(",") if p.strip())
    seen: set[str] = set()
    uniq: list[str] = []
    for x in result:
        if x not in seen:
            uniq.append(x)
            seen.add(x)
    return uniq


# =============================================================================
# SAFE CONVERSION HELPERS
# =============================================================================
EnumT = TypeVar("EnumT", bound=Enum)


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert inputs to ``int`` while handling ``None`` and NaN."""

    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return default
        try:
            return int(float(cleaned))
        except ValueError:
            return default
    return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert inputs to ``float`` while handling ``None`` and NaN."""

    if value is None or (isinstance(value, float) and math.isnan(value)):
        return default
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return default
        try:
            return float(cleaned)
        except ValueError:
            return default
    return default


def safe_enum_convert(
    enum_type: type[EnumT], value: Any, default: EnumT | None = None
) -> EnumT | None:
    """Safely convert value to an enum type, returning ``default`` on failure."""

    try:
        if isinstance(value, enum_type):
            return value
        if isinstance(value, (int, str)):
            return enum_type(value)
        return default
    except (ValueError, TypeError):
        return default


# =============================================================================
# DOMAIN HELPERS
# =============================================================================
def norm_gender(value: Any) -> Gender | None:
    s = normalize_fa(value)
    match s:
        case "1" | "پسر" | "male" | "boy" | "پسرانه":
            return Gender.MALE
        case "0" | "دختر" | "female" | "girl" | "دخترانه":
            return Gender.FEMALE
        case _:
            return None


def gender_text(code: Gender | int | None) -> str:
    gender_map: dict[Gender, str] = {
        Gender.FEMALE: "دختر",
        Gender.MALE: "پسر",
    }
    gender_enum = safe_enum_convert(Gender, code)
    if gender_enum is None:
        return ""
    return gender_map.get(gender_enum, "")


def norm_status(value: Any) -> Status | None:
    s = normalize_fa(value)
    match s:
        case "1" | "دانش آموز" | "دانش‌آموز" | "student":
            return Status.STUDENT
        case "0" | "فارغ" | "فارغ التحصیل" | "فارغ‌التحصیل" | "graduate":
            return Status.GRADUATE
        case _:
            return None


def status_text(code: Status | int | None) -> str:
    status_map: dict[Status, str] = {
        Status.STUDENT: "دانش‌آموز",
        Status.GRADUATE: "فارغ‌التحصیل",
    }
    status_enum = safe_enum_convert(Status, code)
    if status_enum is None:
        return ""
    return status_map.get(status_enum, "")


def center_text(code: Center | int | None) -> str:
    center_map: dict[Center, str] = {
        Center.MARKAZ: "مرکز",
        Center.GOLESTAN: "گلستان",
        Center.SADRA: "صدرا",
    }
    center_enum = safe_enum_convert(Center, code)
    if center_enum is None:
        return ""
    return center_map.get(center_enum, "")


# =============================================================================
# CROSSWALK
# =============================================================================
def _validate_finance_invariants(
    matrix: pd.DataFrame, *, cfg: BuildConfig, finance_col: str
) -> None:
    if finance_col not in matrix.columns:
        return
    finance_variants = cfg.finance_variants or ()
    required = {int(code) for code in finance_variants}
    join_cols = [col for col in cfg.policy.join_keys if col in matrix.columns]
    base_cols = [col for col in join_cols if col != finance_col]
    if not base_cols:
        return

    def _collect(values: pd.Series) -> set[int]:
        return {int(v) for v in values.dropna()}

    grouped = matrix.groupby(base_cols, dropna=False, sort=False)[finance_col].agg(_collect)
    missing = grouped[grouped.apply(lambda present: not required.issubset(present))]
    if not missing.empty:
        details = {
            tuple(key) if isinstance(key, tuple) else key: sorted(required - present)
            for key, present in missing.items()
        }
        raise AssertionError("Finance variants incomplete for join keys: " + str(details))


def _validate_alias_contract(matrix: pd.DataFrame, *, cfg: BuildConfig) -> None:
    alias_series = ensure_series(matrix["جایگزین"]).astype("string").str.strip().fillna("")
    mentor_ids = ensure_series(matrix["کد کارمندی پشتیبان"]).astype("string").str.strip().fillna("")
    row_types = ensure_series(matrix["عادی مدرسه"]).astype("string").str.strip().fillna("")

    school_mask = row_types == "مدرسه‌ای"
    mismatch_school = matrix.loc[school_mask & (alias_series != mentor_ids)]
    if not mismatch_school.empty:
        raise AssertionError("School rows must use mentor_id as alias")

    normal_mask = row_types == "عادی"
    alias_normal = alias_series[normal_mask]
    invalid_pattern = alias_normal[~alias_normal.str.fullmatch(r"\d{4}")]
    if not invalid_pattern.empty:
        raise AssertionError("Normal rows must use 4-digit postal alias")

    postal_range = cfg.postal_valid_range
    if postal_range is None:
        raise ValueError("postal_valid_range is required for alias validation")
    min_postal, max_postal = postal_range
    alias_numeric = alias_normal.map(lambda v: safe_int_value(v, default=0))
    invalid_range = alias_numeric[(alias_numeric < min_postal) | (alias_numeric > max_postal)]
    if not invalid_range.empty:
        raise AssertionError("Postal alias out of configured range")


def _validate_school_code_contract(matrix: pd.DataFrame, *, school_code_col: str) -> None:
    row_types = ensure_series(matrix["عادی مدرسه"]).astype("string").str.strip().fillna("")
    codes = matrix[school_code_col].astype("Int64")
    school_mask = row_types == "مدرسه‌ای"
    if codes[school_mask].isna().any():
        raise AssertionError("School rows must have a school code value")
    if (codes[~school_mask] != 0).any():
        raise AssertionError("Normal rows must have zero school code")


def prepare_crosswalk_mappings(
    crosswalk_groups_df: pd.DataFrame,
    synonyms_df: pd.DataFrame | None = None,
) -> tuple[dict[str, int], dict[int, str], dict[str, list[tuple[str, int]]], dict[str, str]]:
    """ساخت نگاشت‌های موردنیاز از دیتافریم Crosswalk.

    مثال ساده::

        >>> mappings = prepare_crosswalk_mappings(groups_df)  # doctest: +SKIP

    Args:
        crosswalk_groups_df: دیتافریم شیت «پایه تحصیلی (گروه آزمایشی)».
        synonyms_df: دیتافریم شیت «Synonyms» در صورت وجود.

    Returns:
        چهارتایی ``(name_to_code, code_to_name, buckets, synonyms)``.
    """

    required_columns = {"گروه آزمایشی", "کد گروه", "مقطع تحصیلی"}
    missing = required_columns.difference(crosswalk_groups_df.columns)
    if missing:
        raise ValueError(f"ستون‌های الزامی Crosswalk یافت نشد: {sorted(missing)}")

    name_to_code: dict[str, int] = {}
    code_to_name: dict[int, str] = {}
    buckets: dict[str, list[tuple[str, int]]] = {}
    for _, row in crosswalk_groups_df.iterrows():
        gname = str(row["گروه آزمایشی"])
        gcode = int(row["کد گروه"])
        level = str(row["مقطع تحصیلی"])
        name_to_code[normalize_fa(gname)] = gcode
        code_to_name[gcode] = gname
        buckets.setdefault(level, []).append((gname, gcode))

    synonyms = {normalize_fa(k): v for k, v in BUILTIN_SYNONYMS.items()}
    if synonyms_df is not None:
        src_col = next(
            (
                c
                for c in synonyms_df.columns
                if "from" in normalize_fa(c) or "alias" in normalize_fa(c)
            ),
            synonyms_df.columns[0],
        )
        dst_col = next(
            (
                c
                for c in synonyms_df.columns
                if "to" in normalize_fa(c) or "target" in normalize_fa(c)
            ),
            synonyms_df.columns[1] if len(synonyms_df.columns) > 1 else synonyms_df.columns[0],
        )
        for _, row in synonyms_df.iterrows():
            src = normalize_fa(row.get(src_col, ""))
            dst = str(row.get(dst_col, "")).strip()
            if src and dst:
                synonyms[src] = dst

    return name_to_code, code_to_name, buckets, synonyms


# -----------------------------------------------------------------------------
def expand_group_token(
    token: str,
    name_to_code: dict[str, int],
    code_to_name: Mapping[int, str],
    buckets: dict[str, list[tuple[str, int]]],
    synonyms: dict[str, str],
) -> list[tuple[str, int]]:
    """گسترش توکن گروه آزمایشی به زوج‌های (نام، کد) با پشتیبانی از کد عددی.

    مثال::

        >>> mappings = {"یازدهم ریاضی": 27}
        >>> expand_group_token("27", mappings, {27: "یازدهم ریاضی"}, {}, {})
        [('یازدهم ریاضی', 27)]

    Args:
        token: مقدار خام ستون گروه آزمایشی (نام یا کد).
        name_to_code: نگاشت نام نرمال‌شده → کد گروه.
        code_to_name: نگاشت کد → نام گروه برای resolve ورودی عددی.
        buckets: نگاشت عنوان مقطع → لیست زوج‌های (نام، کد).
        synonyms: نگاشت نام/کلید نرمال‌شده → نام/باکت مقصد.

    Returns:
        فهرست یکتا از زوج‌های (نام، کد) به ترتیب کشف‌شده.
    """

    t = normalize_fa(token)
    if not t:
        return []

    out: list[tuple[str, int]] = []

    numeric = _coerce_int_like(t)
    if numeric is not None and numeric in code_to_name:
        out.append((code_to_name[numeric], int(numeric)))

    # 1) Synonym
    if t in synonyms:
        syn = synonyms[t]
        if syn.startswith("__BUCKET__"):
            out.extend(buckets.get(syn.replace("__BUCKET__", ""), []))
        else:
            key = normalize_fa(syn)
            if key in name_to_code:
                out.append((syn, name_to_code[key]))
    # 2) Buckets
    checks = [
        (["متوسطه1", "متوسطه اول"], "متوسطه اول"),
        (["متوسطه2", "متوسطه دوم"], "متوسطه دوم"),
        (["دبستان"], "دبستان"),
        (["هنرستان"], "هنرستان"),
        (["کنکوری"], "کنکوری"),
    ]
    for kws, bucket in checks:
        if any(k in t for k in kws):
            out.extend(buckets.get(bucket, []))
    # 3) grade × major
    for num, name in [("10", "دهم"), ("11", "یازدهم"), ("12", "دوازدهم")]:
        if name in t or num in t:
            for kw, pretty in [
                ("تجربی", "تجربی"),
                ("ریاضی", "ریاضی"),
                ("انسانی", "انسانی"),
                ("علوم و معارف اسلامی", "علوم و معارف اسلامی"),
            ]:
                if normalize_fa(kw) in t:
                    title = f"{name} {pretty}".strip()
                    key = normalize_fa(title)
                    if key in name_to_code:
                        out.append((title, name_to_code[key]))
    # 4) direct
    if not out and t in name_to_code:
        out.append((token, name_to_code[t]))

    # dedup by code
    seen = set()
    uniq: list[tuple[str, int]] = []
    for n, c in out:
        if c not in seen:
            uniq.append((n, c))
            seen.add(c)
    return uniq


# =============================================================================
# SCHOOL MAPPINGS
# =============================================================================
def build_school_maps(
    schools_df: pd.DataFrame, *, cfg: BuildConfig | None = None
) -> tuple[dict[str, str], dict[str, str]]:
    """ساخت نگاشت‌های کد ↔ نام مدرسه با نرمال‌سازی عددی پایدار."""

    schools_df = ensure_required_columns(schools_df, {COL_SCHOOL_CODE}, "school")
    cfg = cfg or BuildConfig()
    name_cols = [c for c in schools_df.columns if "نام مدرسه" in c]
    if not name_cols:
        raise ValueError("ستون نام مدرسه در SchoolReport یافت نشد")

    code_to_name: dict[str, str] = {}
    name_to_code: dict[str, str] = {}
    for _, r in schools_df.iterrows():
        normalized_code = str(school_code_norm(r[COL_SCHOOL_CODE], cfg=cfg))
        primary_name = str(r[name_cols[0]])
        code_to_name.setdefault(normalized_code, primary_name)
        for col in name_cols:
            nm = normalize_fa(r[col])
            if nm:
                name_to_code.setdefault(nm, normalized_code)

    return code_to_name, name_to_code


def safe_int_column(df: pd.DataFrame, col: str, default: int = 0) -> pd.Series:
    """تبدیل ستونی از DataFrame به نوع صحیح بدون تبدیل موقت به float."""

    series = df.get(col)
    if series is None:
        return pd.Series([int(default)] * len(df), index=df.index, dtype="Int64")
    coerced = series.map(_coerce_int_like)
    result = pd.Series(coerced, index=series.index, dtype="Int64")
    if default is not None:
        result = result.fillna(int(default))
    return result


def safe_int_value(value: Any, default: int = 0) -> int:
    """تبدیل ورودی به عدد صحیح با مدیریت مقادیر خالی.

    مثال ساده::

        >>> safe_int_value("7")
        7
        >>> safe_int_value("", default=2)
        2

    Args:
        value: مقداری که باید به int تبدیل شود.
        default: مقدار پیش‌فرض در صورت عدم امکان تبدیل.

    Returns:
        مقدار صحیح نرمال‌شده (حداقل برابر با ``default``).
    """

    text = to_numlike_str(value).strip()
    if text and text.lstrip("-").isdigit():
        try:
            return int(text)
        except (ValueError, TypeError, OverflowError):
            pass
    return int(default)


def normalize_capacity_values(
    current: Any, special: Any, *, default: int = 0
) -> tuple[int, int, int]:
    """نرمال‌سازی ستون‌های ظرفیت و محاسبهٔ ظرفیت باقی‌مانده.

    مثال::

        >>> normalize_capacity_values("5", "12")
        (5, 12, 7)

    Args:
        current: مقدار پوشش فعلی در Inspactor.
        special: ظرفیت ویژهٔ ثبت‌شده برای پشتیبان.
        default: مقدار جایگزین برای ورودی‌های نامعتبر.

    Returns:
        سه‌تایی ``(covered_now, special_limit, remaining_capacity)``.
    """

    covered = max(safe_int_value(current, default=default), 0)
    special_limit = max(safe_int_value(special, default=default), 0)
    remaining = max(special_limit - covered, 0)
    return covered, special_limit, remaining


# =============================================================================
# CAPACITY GATE (R0)
# =============================================================================


@dataclass(frozen=True)
class CapacityGateMetrics:
    """معیارهای خلاصهٔ مرحلهٔ R0 با مثال ساده.

    مثال::

        >>> CapacityGateMetrics(
        ...     total_removed=2, total_special_capacity_lost=7, percent_pool_kept=0.5
        ... )
        CapacityGateMetrics(total_removed=2, total_special_capacity_lost=7, percent_pool_kept=0.5)
    """

    total_removed: int = 0
    total_special_capacity_lost: int = 0
    percent_pool_kept: float = 1.0

    @classmethod
    def empty(cls) -> CapacityGateMetrics:
        """ساخت نمونهٔ تهی برای زمانی که R0 اجرا نشده است."""

        return cls()


def capacity_gate(
    insp: pd.DataFrame,
    *,
    cfg: BuildConfig,
    progress: ProgressFn = noop_progress,
) -> tuple[pd.DataFrame, pd.DataFrame, CapacityGateMetrics, bool]:
    current_col = cfg.capacity_current_column or CAPACITY_CURRENT_COL
    special_col = cfg.capacity_special_column or CAPACITY_SPECIAL_COL

    if current_col not in insp.columns or special_col not in insp.columns:
        progress(10, "capacity columns missing; skipping capacity gate")
        return insp.copy(), pd.DataFrame(), CapacityGateMetrics.empty(), True

    df = insp.copy()
    df["_cap_cur"] = safe_int_column(df, current_col, default=0)
    df["_cap_spec"] = safe_int_column(df, special_col, default=0)

    removed_mask = ~(df["_cap_cur"] < df["_cap_spec"])
    total_pool = len(df.index)
    removed_count = int(removed_mask.sum())
    special_capacity_lost = int(df.loc[removed_mask, "_cap_spec"].sum())
    kept_count = total_pool - removed_count
    percent_pool_kept = (kept_count / total_pool) if total_pool else 1.0
    metrics = CapacityGateMetrics(
        total_removed=removed_count,
        total_special_capacity_lost=special_capacity_lost,
        percent_pool_kept=percent_pool_kept,
    )

    keep_cols = [COL_MENTOR_NAME, COL_MANAGER_NAME, current_col, special_col]
    if COL_SCHOOL1 in df.columns:
        keep_cols.append(COL_SCHOOL1)
    if COL_GROUP in df.columns:
        keep_cols.append(COL_GROUP)

    removed = df.loc[removed_mask, keep_cols].copy()
    removed = removed.rename(
        columns={
            current_col: "تحت پوشش فعلی",
            special_col: "ظرفیت خاص",
            COL_MENTOR_NAME: "پشتیبان",
            COL_MANAGER_NAME: "مدیر",
            COL_SCHOOL1: "مدرسه (خام)",
            COL_GROUP: "گروه آزمایشی (خام)",
        }
    )
    removed["دلیل حذف"] = "تعداد داوطلبان تحت پوشش ≥ تعداد تحت پوشش خاص"

    kept = df.loc[~removed_mask].copy()
    drop_cols = ["_cap_cur", "_cap_spec"]
    kept = kept.drop(columns=drop_cols, errors="ignore")
    removed = removed.drop(columns=drop_cols, errors="ignore")

    progress(
        20,
        (
            "capacity gate kept="
            f"{len(kept)} removed={len(removed)} kept_pct={metrics.percent_pool_kept:.1%}"
        ),
    )
    return kept, removed, metrics, False


# =============================================================================
# SCHOOL CODE EXTRACTION
# =============================================================================


@dataclass(frozen=True)
class MentorSchoolBindingInfo:
    """متادیتای وضعیت مدرسهٔ پشتیبان (global یا restricted)."""

    codes: list[int]
    has_school_constraint: bool
    binding_mode: str


def to_int_str_or_none(value: Any) -> str | None:
    parsed = _coerce_int_like(value)
    if parsed is None or parsed == 0:
        return None
    return str(parsed)


def collect_school_codes_from_row(
    r: pd.Series,
    name_to_code: dict[str, str],
    school_cols: list[str],
    *,
    cfg: BuildConfig,
    binding_policy: MentorSchoolBindingPolicy,
) -> MentorSchoolBindingInfo:
    """استخراج کدهای مدرسه و تعیین mode (global/restricted)."""

    normalized_codes: list[int] = []
    seen: set[int] = set()
    has_reference = False
    for col in school_cols:
        raw = r.get(col)
        if binding_policy.is_empty_value(raw):
            continue
        has_reference = True
        candidate = to_int_str_or_none(raw)
        if candidate is None:
            candidate = name_to_code.get(normalize_fa(raw), None)
        normalized = school_code_norm(candidate, cfg=cfg)
        if normalized > 0 and normalized not in seen:
            normalized_codes.append(normalized)
            seen.add(normalized)
    return MentorSchoolBindingInfo(
        codes=normalized_codes,
        has_school_constraint=has_reference,
        binding_mode=binding_policy.binding_mode(has_reference),
    )


# =============================================================================
# PROGRESS (optional)
# =============================================================================
T = TypeVar("T")

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False


def progress(it: Iterable[T], total: int | None = None) -> Iterable[T]:
    return tqdm(it, total=total) if HAS_TQDM else it


# =============================================================================
# GROUP CODE PARSING
# =============================================================================
def parse_group_code_spec(
    spec: Any,
    *,
    valid_codes: Collection[int] | None = None,
    invalid_collector: list[int] | None = None,
) -> list[int]:
    """تبدیل رشتهٔ ورودی به فهرست کد گروه‌های معتبر.

    مثال::

        >>> parse_group_code_spec("27,31:35", valid_codes={27, 31, 33, 35})
        [27, 31, 33, 35]

    Args:
        spec: ورودی خام از ستون «شامل گروه های آزمایشی».
        valid_codes: مجموعهٔ کدهای مجاز برای فیلتر کردن خروجی.
        invalid_collector: لیست اختیاری برای ثبت کدهای نامعتبر.

    Returns:
        لیست یکتا از کدهای معتبر به ترتیب مشاهده‌شده.
    """

    if spec is None or (isinstance(spec, float) and math.isnan(spec)):
        return []

    s = str(spec).strip()
    if not s:
        return []

    s = s.translate(_TRANS_PERSIAN_DIGITS)
    parts = _RE_SPLIT_ITEMS.split(s)
    out: list[int] = []
    seen: set[int] = set()
    valid_set = set(valid_codes) if valid_codes is not None else None
    invalid_seen: set[int] = set()

    def _register(value: int) -> None:
        if valid_set is not None and value not in valid_set:
            if invalid_collector is not None and value not in invalid_seen:
                invalid_collector.append(value)
                invalid_seen.add(value)
            return
        if value not in seen:
            out.append(value)
            seen.add(value)

    for tok in parts:
        tok = tok.strip()
        if not tok:
            continue
        m = _RE_RANGE.match(tok)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a > b:
                a, b = b, a
            for value in range(a, b + 1):
                _register(value)
            continue
        if tok.isdigit():
            _register(int(tok))

    return out


# =============================================================================
# ROW GENERATION
# =============================================================================
def generate_row_variants(
    base: dict[str, Any],
    group_pairs: list[tuple[str, int]],
    genders: list[Any],
    statuses: list[Any],
    schools_raw: list[Any],
    finance_variants: Iterable[int],
    code_to_name_school: dict[str, str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def _school_lookup(sc_val: Any) -> tuple[str, str, int]:
        """returns (school_code, school_name, is_school_flag)
        Patch: empty -> ("0", "", 0) so output column «کد مدرسه» becomes 0.
        """
        # If empty → set school code to 0 (string to keep type consistent across DataFrame)
        if sc_val is None or str(sc_val).strip() == "":
            return "0", "", 0
        s = str(sc_val).strip()
        if s.isdigit():
            return s, code_to_name_school.get(s, ""), 1
        return "", str(sc_val), 0

    iter_genders = genders or [""]
    iter_statuses = statuses or [""]
    iter_schools = schools_raw if any(schools_raw) else [""]

    for (g_name, g_code), ge, st, fin, sc in product(
        group_pairs, iter_genders, iter_statuses, finance_variants, iter_schools
    ):
        gcode = norm_gender(ge) if ge != "" else None
        stcode = norm_status(st) if st != "" else None
        school_code, school_name, is_school = _school_lookup(sc)

        alias_val = base.get("alias", "")

        rows.append(
            {
                "جایگزین": int(alias_val) if str(alias_val).strip().isdigit() else str(alias_val),
                "پشتیبان": base["supporter"],
                "کد کارمندی پشتیبان": base["mentor_id"],
                "مدیر": base["manager"],
                "ردیف پشتیبان": (
                    int(base["row_id"]) if str(base["row_id"]).strip().isdigit() else ""
                ),
                "نام رشته": g_name,
                "کدرشته": int(g_code),
                "جنسیت": int(gcode) if gcode is not None else "",
                "دانش آموز فارغ": int(stcode) if stcode is not None else "",
                "مرکز گلستان صدرا": int(base["center_code"]),
                "مالی حکمت بنیاد": int(fin),
                "کد مدرسه": school_code,
                "عادی مدرسه": "مدرسه‌ای" if is_school else "عادی",
                "نام مدرسه": school_name,
                "جنسیت2": gender_text(gcode),
                "دانش آموز فارغ2": status_text(stcode),
                "مرکز گلستان صدرا3": base["center_text"],
                CAPACITY_CURRENT_COL: safe_int(base.get("capacity_current", 0)),
                CAPACITY_SPECIAL_COL: safe_int(base.get("capacity_special", 0)),
                "remaining_capacity": safe_int(base.get("capacity_remaining", 0)),
            }
        )
    return rows


# =============================================================================
# VECTORIZED MATRIX ASSEMBLY HELPERS
# =============================================================================


def _prepare_base_rows(
    insp: pd.DataFrame,
    *,
    cfg: BuildConfig,
    name_to_code: dict[str, int],
    code_to_name: dict[int, str],
    buckets: dict[str, list[tuple[str, int]]],
    synonyms: dict[str, str],
    school_name_to_code: dict[str, str],
    code_to_name_school: dict[str, str],
    group_cols: list[str],
    school_cols: list[str],
    gender_col: str | None,
    included_col: str | None,
) -> tuple[pd.DataFrame, list[dict[str, Any]], list[dict[str, Any]]]:
    records: list[dict[str, Any]] = []
    unseen_groups: list[dict[str, Any]] = []
    unmatched_schools: list[dict[str, Any]] = []

    finance_variants = list(finance_cross(cfg.finance_variants, cfg=cfg))
    normal_statuses = [int(s) for s in cfg.policy.normal_statuses]
    school_statuses = [int(s) for s in cfg.policy.school_statuses]
    postal_col = cfg.postal_code_column or COL_POSTAL
    capacity_current_col = cfg.capacity_current_column or CAPACITY_CURRENT_COL
    capacity_special_col = cfg.capacity_special_column or CAPACITY_SPECIAL_COL
    binding_policy = cfg.policy.mentor_school_binding

    for row in insp.to_dict(orient="records"):
        mentor_id_raw = row.get(COL_MENTOR_ID, "")
        mentor_id = str(mentor_id_raw).strip()
        if not mentor_id:
            continue

        if COL_CAN_ALLOC in row:
            can_alloc = str(row.get(COL_CAN_ALLOC, "")).strip() in cfg.can_allocate_truthy
            if not can_alloc:
                continue

        mentor_name = str(row.get(COL_MENTOR_NAME, "")).strip()
        manager_name = str(row.get(COL_MANAGER_NAME, "")).strip()
        postal_raw = row.get(postal_col, "")

        school_binding = collect_school_codes_from_row(
            pd.Series(row),
            school_name_to_code,
            school_cols,
            cfg=cfg,
            binding_policy=binding_policy,
        )
        school_codes = school_binding.codes
        has_school_constraint = school_binding.has_school_constraint
        school_count = safe_int_value(row.get(COL_SCHOOL_COUNT, 0), default=0)

        covered_now, special_limit, remaining_capacity = normalize_capacity_values(
            row.get(capacity_current_col, 0),
            row.get(capacity_special_col, 0),
        )

        genders_raw = ensure_list([row.get(gender_col)]) if gender_col else [""]
        gender_codes: list[int | str] = []
        for token in genders_raw:
            token_str = str(token).strip()
            if not token_str:
                gender_codes.append("")
                continue
            normalized = norm_gender(token_str)
            if normalized is None:
                gender_codes.append("")
            else:
                gender_codes.append(int(normalized))

        raw_groups = ensure_list([row[c] for c in group_cols]) if group_cols else []
        group_pairs: list[tuple[str, int]] = []
        used_included = False
        row_unseen_tokens: list[str] = []

        if included_col:
            invalid_codes: list[int] = []
            codes = parse_group_code_spec(
                row.get(included_col),
                valid_codes=code_to_name.keys(),
                invalid_collector=invalid_codes,
            )
            if codes or invalid_codes:
                used_included = True
            for gc in codes:
                group_pairs.append((code_to_name[gc], gc))
            row_unseen_tokens.extend(f"code:{gc}" for gc in invalid_codes)

        if not used_included:
            expanded: list[tuple[str, int]] = []
            for tok in raw_groups or []:
                ex = expand_group_token(tok, name_to_code, code_to_name, buckets, synonyms)
                if not ex:
                    row_unseen_tokens.append(str(tok))
                expanded.extend(ex)
            seen_codes: set[int] = set()
            for name, code in expanded:
                if code not in seen_codes:
                    group_pairs.append((name, code))
                    seen_codes.add(code)

        if not group_pairs:
            tokens = list(dict.fromkeys(row_unseen_tokens or [""]))
            for token in tokens:
                unseen_groups.append(
                    {"group_token": token, "supporter": mentor_name, "manager": manager_name}
                )
            continue

        alias_normal_raw = compute_alias(MentorType.NORMAL, postal_raw, mentor_id, cfg=cfg)
        alias_school_raw = compute_alias(MentorType.SCHOOL, postal_raw, mentor_id, cfg=cfg)
        alias_normal_num = _num_to_int_safe(alias_normal_raw)
        alias_normal_valid = alias_normal_num is None or alias_normal_num >= 1000
        alias_normal = alias_normal_raw if alias_normal_valid else None
        alias_school = alias_school_raw or None

        mentor_mode = classify_mentor_mode(
            postal_code=postal_raw,
            school_codes=school_codes,
            cfg=cfg,
            has_school_constraint=has_school_constraint,
            school_count=school_count,
            binding_policy=binding_policy,
            aliases=(alias_normal_raw, alias_school_raw),
        )

        center = domain_center_from_manager(manager_name, cfg=cfg)

        base = {
            "supporter": mentor_name,
            "manager": manager_name,
            "mentor_id": mentor_id,
            "mentor_row_id": row.get(COL_MENTOR_ROWID, ""),
            "center_code": int(center),
            "center_text": center_text(int(center)),
            "group_pairs": group_pairs,
            "genders": gender_codes or [""],
            "school_codes": school_codes,
            "schools_normal": [""],
            "finance": finance_variants,
            "statuses_normal": normal_statuses,
            "statuses_school": school_statuses,
            "alias_normal": alias_normal,
            "alias_school": alias_school,
            "mentor_school_binding_mode": school_binding.binding_mode,
            "has_school_constraint": has_school_constraint,
            "can_normal": mentor_mode in (MentorType.NORMAL, MentorType.DUAL)
            and bool(alias_normal),
            "can_school": mentor_mode in (MentorType.SCHOOL, MentorType.DUAL)
            and bool(alias_school),
            "capacity_current": covered_now,
            "capacity_special": special_limit,
            "capacity_remaining": remaining_capacity,
            "school_count": school_count,
        }

        for sc in school_codes:
            if str(sc) not in code_to_name_school:
                unmatched_schools.append(
                    {"raw_school": str(sc), "supporter": mentor_name, "manager": manager_name}
                )

        records.append(base)

    base_df = pd.DataFrame(records)
    required_flags = {
        "mentor_school_binding_mode": binding_policy.global_mode,
        "has_school_constraint": False,
        "can_normal": False,
        "can_school": False,
    }
    for col, default in required_flags.items():
        if col not in base_df.columns:
            base_df[col] = default
    return base_df, unseen_groups, unmatched_schools


def _detect_school_lookup_mismatches(
    insp: pd.DataFrame,
    *,
    school_columns: Sequence[str],
    code_to_name_school: Mapping[str, str],
    school_name_to_code: Mapping[str, str],
    binding_policy: MentorSchoolBindingPolicy | None = None,
) -> tuple[pd.DataFrame, int, int]:
    """بررسی مقادیر ستون‌های نام مدرسه و ثبت مقادیر ناشناخته."""

    columns = [col for col in school_columns if col in insp.columns]
    binding = binding_policy or MentorSchoolBindingPolicy()
    if not columns:
        return (
            pd.DataFrame(
                columns=[
                    "row_index",
                    "پشتیبان",
                    "مدیر",
                    "reason",
                    "school_column",
                    "school_value",
                    "raw_school_value",
                    "source_index",
                ]
            ),
            0,
            0,
        )

    row_positions = {idx: pos + 1 for pos, idx in enumerate(insp.index)}
    issues: list[dict[str, object]] = []
    total_refs = 0
    for column in columns:
        series = insp[column]
        for idx, raw_value in series.items():
            if binding.is_empty_value(raw_value):
                continue
            total_refs += 1
            reason: str | None = None
            text = str(raw_value).strip()
            candidate = to_int_str_or_none(text)
            normalized_display = text
            if candidate is not None:
                normalized_display = candidate
                if candidate not in code_to_name_school:
                    reason = f"unknown school code ({text})"
            else:
                normalized = normalize_fa(text)
                normalized_display = normalized or text
                if normalized and normalized not in school_name_to_code:
                    reason = f"unknown school name ({text})"
            if reason is None:
                continue
            mentor = insp.at[idx, COL_MENTOR_NAME] if COL_MENTOR_NAME in insp.columns else ""
            manager = insp.at[idx, COL_MANAGER_NAME] if COL_MANAGER_NAME in insp.columns else ""
            issues.append(
                {
                    "row_index": row_positions.get(idx, 0),
                    "پشتیبان": mentor,
                    "مدیر": manager,
                    "reason": reason,
                    "school_column": column,
                    "school_value": normalized_display,
                    "raw_school_value": text,
                    "source_index": idx,
                }
            )

    frame = pd.DataFrame(issues)
    return frame, len(issues), total_refs


def _filter_invalid_mentors(
    insp: pd.DataFrame,
    *,
    cfg: BuildConfig,
    gender_col: str | None,
    included_col: str | None,
    group_cols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove mentor rows with missing identifiers or negative capacity.

    Duplicate mentor IDs with distinct join profiles are tolerated; exact
    duplicate profiles are handled later by deterministic deduplication and QA
    reporting rather than invalidation at this stage.
    """

    mentor_source = ensure_series(insp[COL_MENTOR_ID])
    mentor_id_series = mentor_source.astype("string").fillna("").str.strip()
    invalid_mask = mentor_id_series.eq("")

    invalid_entries: list[pd.DataFrame] = []

    def _collect_invalid_rows(mask: pd.Series, reason: str) -> None:
        if not mask.any():
            return
        invalid_entries.append(
            pd.DataFrame(
                {
                    "row_index": (insp.index[mask] + 1),
                    "پشتیبان": insp.loc[mask, COL_MENTOR_NAME],
                    "مدیر": insp.loc[mask, COL_MANAGER_NAME],
                    "reason": reason,
                }
            )
        )

    _collect_invalid_rows(invalid_mask, "missing mentor employee code")

    valid_mask = ~invalid_mask

    remaining_col = cfg.remaining_capacity_column or "remaining_capacity"
    negative_capacity_mask = pd.Series(False, index=insp.index)
    if remaining_col in insp.columns:
        remaining_series = pd.to_numeric(ensure_series(insp[remaining_col]), errors="coerce")
        negative_capacity_mask = remaining_series.lt(0).fillna(False)
    negative_capacity_mask &= valid_mask

    _collect_invalid_rows(negative_capacity_mask, "negative remaining capacity")

    valid_mask = valid_mask & ~(negative_capacity_mask)

    insp_valid = insp.loc[valid_mask].copy()

    if invalid_entries:
        invalid_df = pd.concat(invalid_entries, ignore_index=True)
    else:
        invalid_df = pd.DataFrame(columns=["row_index", "پشتیبان", "مدیر", "reason"])

    return insp_valid, invalid_df


def _explode_rows(
    base: pd.DataFrame,
    *,
    alias_col: str,
    status_col: str,
    school_col: str,
    type_label: str,
    code_to_name_school: dict[str, str],
    cfg: BuildConfig,
    cap_current_col: str,
    cap_special_col: str,
    remaining_col: str,
    school_code_col: str,
) -> pd.DataFrame:

    def _build_school_code_series(values: pd.Series, index: pd.Index) -> pd.Series:
        """تولید ستون «کد مدرسه» با dtype یکنواخت ``Int64`` بدون هشدارهای آیندهٔ pandas.

        مثال::

            >>> _build_school_code_series(pd.Series([None, "4001"]), pd.RangeIndex(2))
            0       0
            1    4001
            dtype: Int64
        """

        numeric = pd.Series(values.map(_coerce_int_like), index=index, dtype="Int64")
        return numeric.fillna(0).astype("Int64")

    if base.empty:
        return pd.DataFrame()

    df = base.copy()
    df = df.loc[df[alias_col].notna()]
    if df.empty:
        return pd.DataFrame()

    df = df.assign(finance_list=df["finance"], school_list=df[school_col])
    df = df.drop(columns=["finance", school_col])
    df = df.explode("group_pairs")
    gp = pd.DataFrame(
        df.pop("group_pairs").tolist(),
        columns=["group_name", "group_code"],
        index=df.index,
    )
    df = df.join(gp)

    def _statuses_for_row(row: pd.Series) -> tuple[int, ...]:
        configured_raw = row.get(status_col, [])
        configured_iterable: Iterable[Any]
        if isinstance(configured_raw, Iterable) and not isinstance(configured_raw, (str, bytes)):
            configured_iterable = configured_raw
        else:
            configured_iterable = ()

        configured = tuple(
            int(value) for value in configured_iterable if _coerce_int_like(value) is not None
        )

        group_value = _coerce_int_like(row.get("group_code"))
        group_int = int(group_value) if group_value is not None else 0
        allowed = allowed_statuses_for_group(group_int, is_school_branch=type_label == "مدرسه‌ای")
        filtered = tuple(status for status in configured if status in allowed)
        return filtered if filtered else allowed

    df["status_seq"] = df.apply(_statuses_for_row, axis=1)
    df = df.explode("genders").explode("status_seq").explode("school_list").explode("finance_list")

    if df.empty:
        return pd.DataFrame()

    def _optional_int(value: Any) -> int | None:
        """تبدیل مقدار به عدد صحیح در صورت امکان و بازگرداندن ``None`` برای تهی.

        این تابع صرفاً تبدیل را انجام می‌دهد و نگاشت «تهی → صفر» را به لایهٔ فراخوان
        می‌سپارد تا فقط برای کلیدهای join که Policy/SSoT آن را مجاز می‌دانند اعمال شود.
        """

        return _coerce_int_like(value)

    def _normalize_demographic_key(series: pd.Series) -> pd.Series:
        """نرمال‌سازی جنسیت/وضعیت فارغ‌التحصیلی مطابق فضای کاندید (تهی → صفر).

        نمونه::

            >>> _normalize_demographic_key(pd.Series(["", pd.NA, 1]))
            0    0
            1    0
            2    1
            dtype: Int64
        """

        normalized = pd.Series(series.map(_optional_int), index=series.index, dtype="Int64")
        return normalized.fillna(0).astype("Int64")

    gender_series = df["genders"]
    df["gender_code"] = _normalize_demographic_key(gender_series)

    status_series = df["status_seq"]
    df["status_code"] = _normalize_demographic_key(status_series)

    blank_school_mask = df["school_list"].map(
        lambda v: pd.isna(v) or (isinstance(v, str) and not v.strip())
    )
    df["کد مدرسه"] = _build_school_code_series(df["school_list"], df.index)
    df.loc[blank_school_mask.fillna(True), "کد مدرسه"] = 0
    df["کد مدرسه"] = df["کد مدرسه"].astype("Int64")
    df["نام مدرسه"] = df["کد مدرسه"].astype(str).map(code_to_name_school).fillna("")
    if school_code_col != "کد مدرسه":
        df = df.rename(columns={"کد مدرسه": school_code_col})
        school_code_display = school_code_col
    else:
        school_code_display = "کد مدرسه"

    alias_series = df[alias_col]
    df["جایگزین"] = alias_series.map(to_numlike_str)

    df = df.drop(columns=["genders", status_col, "status_seq", "school_list", alias_col])
    df["عادی مدرسه"] = type_label

    df = df.rename(
        columns={
            "supporter": "پشتیبان",
            "mentor_id": "کد کارمندی پشتیبان",
            "manager": "مدیر",
            "mentor_row_id": "ردیف پشتیبان",
            "group_name": "نام رشته",
            "group_code": "کدرشته",
            "center_code": "مرکز گلستان صدرا",
            "finance_list": "مالی حکمت بنیاد",
        }
    )

    df[cap_current_col] = safe_int_column(df, "capacity_current")
    df[cap_special_col] = safe_int_column(df, "capacity_special")
    df[remaining_col] = safe_int_column(df, "capacity_remaining")

    df["مالی حکمت بنیاد"] = safe_int_column(df, "مالی حکمت بنیاد")
    df["جنسیت"] = df["gender_code"].astype("Int64")
    df["دانش آموز فارغ"] = df["status_code"].astype("Int64")
    df["مرکز گلستان صدرا"] = safe_int_column(df, "مرکز گلستان صدرا", default=0)
    df["کدرشته"] = safe_int_column(df, "کدرشته", default=0)
    df["جنسیت2"] = df["جنسیت"].map(lambda v: gender_text(v) if pd.notna(v) else "")
    df["دانش آموز فارغ2"] = df["دانش آموز فارغ"].map(
        lambda v: status_text(v) if pd.notna(v) else ""
    )
    df["مرکز گلستان صدرا3"] = df["center_text"]

    df = df.drop(
        columns=[
            "gender_code",
            "status_code",
            "center_text",
            "capacity_current",
            "capacity_special",
            "capacity_remaining",
        ],
        errors="ignore",
    )

    binding_policy = cfg.policy.mentor_school_binding
    if "mentor_school_binding_mode" not in df.columns:
        df["mentor_school_binding_mode"] = binding_policy.global_mode
    else:
        df["mentor_school_binding_mode"] = (
            df["mentor_school_binding_mode"].astype("string").fillna(binding_policy.global_mode)
        )
    if "has_school_constraint" not in df.columns:
        df["has_school_constraint"] = False
    else:
        df["has_school_constraint"] = df["has_school_constraint"].fillna(False).astype(bool)
    ordered_columns = [
        "جایگزین",
        "پشتیبان",
        "کد کارمندی پشتیبان",
        "مدیر",
        "ردیف پشتیبان",
        "نام رشته",
        "کدرشته",
        "جنسیت",
        "دانش آموز فارغ",
        "مرکز گلستان صدرا",
        "مالی حکمت بنیاد",
        school_code_display,
        "نام مدرسه",
        "عادی مدرسه",
        "mentor_school_binding_mode",
        "has_school_constraint",
        "جنسیت2",
        "دانش آموز فارغ2",
        "مرکز گلستان صدرا3",
        cap_current_col,
        cap_special_col,
        remaining_col,
    ]
    result = df[ordered_columns]
    if not result.empty:
        dedupe_cols = [
            col
            for col in (
                "جایگزین",
                "کد کارمندی پشتیبان",
                "کدرشته",
                "گروه آزمایشی",
                "جنسیت",
                "دانش آموز فارغ",
                cfg.policy.stage_column("center"),
                cfg.policy.stage_column("finance"),
                school_code_col,
            )
            if col in result.columns
        ]
        if dedupe_cols:
            result = result.drop_duplicates(subset=dedupe_cols, keep="first")
    return result


# =============================================================================
# BUILD MATRIX
# =============================================================================
def build_matrix(
    insp_df: pd.DataFrame,
    schools_df: pd.DataFrame,
    crosswalk_groups_df: pd.DataFrame,
    *,
    crosswalk_synonyms_df: pd.DataFrame | None = None,
    cfg: BuildConfig = BuildConfig(),
    progress: ProgressFn = noop_progress,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:
    """ساخت ماتریس اهلیت بر مبنای دیتافریم‌های ورودی.

    مثال ساده::

        >>> matrix, *_ = build_matrix(insp_df, schools_df, crosswalk_df)  # doctest: +SKIP

    Args:
        insp_df: دیتافریم خام گزارش Inspactor.
        schools_df: دیتافریم نگاشت مدارس.
        crosswalk_groups_df: دیتافریم گروه‌های آزمایشی.
        crosswalk_synonyms_df: دیتافریم نگاشت نام‌های مترادف.
        cfg: پیکربندی ساخت ماتریس.
        progress: تابع پیشرفت تزریق‌شده از لایهٔ زیرساخت.

    Returns:
        هشت‌تایی دیتافریم شامل ماتریس، گزارش QA، لاگ پیشرفت و جداول کنترلی.
    """
    progress_rows: list[dict[str, Any]] = []
    normalization_meta: dict[str, dict[str, Any]] = {}

    def _append_progress_row(row: dict[str, Any]) -> None:
        progress_rows.append(row)

    def _collect_normalization(dataset: str) -> Callable[[ColumnNormalizationReport], None]:
        def _collector(report: ColumnNormalizationReport) -> None:
            alias_list = list(report.aliases_added)
            unmatched_list = list(report.unmatched)
            renamed_pairs = dict(report.renamed)
            normalization_meta[dataset] = {
                "aliases_added": alias_list,
                "renamed_columns": renamed_pairs,
                "unmatched_columns": unmatched_list,
            }
            _append_progress_row(
                {
                    "step": f"normalize_{dataset}",
                    "pct": pd.NA,
                    "message": f"column normalization completed for {dataset}",
                    "status": "ok",
                    "dataset": dataset,
                    "aliases_added_count": len(alias_list),
                    "aliases_added": ", ".join(alias_list),
                    "unmatched_columns_count": len(unmatched_list),
                    "unmatched_columns": ", ".join(unmatched_list),
                    "renamed_columns_count": len(renamed_pairs),
                    "renamed_columns": ", ".join(
                        f"{src}->{dst}" for src, dst in sorted(renamed_pairs.items())
                    ),
                }
            )

        return _collector

    try:
        insp_df = assert_inspactor_schema(insp_df, cfg.policy)
    except KeyError as exc:
        schema_reason = str(exc)
        schema_invalid = pd.DataFrame(
            [
                {
                    "row_index": 0,
                    "پشتیبان": "",
                    "مدیر": "",
                    "reason": schema_reason,
                }
            ]
        )
        setattr(exc, "invalid_mentors_df", schema_invalid)
        raise
    insp_df, _ = normalize_input_columns(
        insp_df,
        kind="InspactorReport",
        collector=_collect_normalization("inspactor"),
    )
    school_name_columns = [
        column for column in insp_df.columns if column.strip().startswith("نام مدرسه")
    ]
    insp_df = canonicalize_pool_frame(
        insp_df,
        policy=cfg.policy,
        sanitize_pool=False,
        pool_source="inspactor",
        require_join_keys=False,
        preserve_columns=school_name_columns,
        # مطابق سیاست، تنها تکرار یک پشتیبان روی همان شش‌کلید ممنوع است؛
        # حضور پشتیبان‌های متفاوت روی یک کلید مجاز است.
        include_distinct_mentor_duplicates=False,
    )
    pool_stats = insp_df.attrs.get("pool_canonicalization_stats")
    alias_autofill = int(getattr(pool_stats, "alias_autofill", 0) or 0) if pool_stats else 0
    alias_unmatched = int(getattr(pool_stats, "alias_unmatched", 0) or 0) if pool_stats else 0
    duplicate_join_keys_df = insp_df.attrs.get(POOL_JOIN_KEY_DUPLICATES_ATTR)
    if duplicate_join_keys_df is None:
        columns = list(cfg.policy.join_keys) + [
            COL_MENTOR_ID,
            "duplicate_group_size",
            "pool_row_index",
            "pool_source",
        ]
        duplicate_join_keys_df = pd.DataFrame(columns=columns)
    duplicate_summary = insp_df.attrs.get(POOL_DUPLICATE_SUMMARY_ATTR)
    duplicate_progress_message = _format_duplicate_progress_preview(
        duplicate_summary,
        join_keys=cfg.policy.join_keys,
        mentor_column=COL_MENTOR_ID,
    )
    if duplicate_progress_message:
        progress(4, f"⚠️ duplicate join keys detected: {duplicate_progress_message}")
    schools_df = resolve_aliases(schools_df, "school")
    schools_df = coerce_semantics(schools_df, "school")
    schools_df = ensure_required_columns(schools_df, REQUIRED_SCHOOL_COLUMNS, "school")
    schools_df, _ = normalize_input_columns(
        schools_df,
        kind="SchoolReport",
        collector=_collect_normalization("schools"),
    )

    progress(5, "preparing crosswalk mappings")
    crosswalk_groups_df, _ = normalize_input_columns(
        crosswalk_groups_df,
        kind="CrosswalkReport",
        include_alias=False,
        report=False,
        collector=_collect_normalization("crosswalk"),
    )
    name_to_code, code_to_name, buckets, synonyms = prepare_crosswalk_mappings(
        crosswalk_groups_df,
        crosswalk_synonyms_df,
    )
    code_to_name_school, school_name_to_code = build_school_maps(schools_df, cfg=cfg)
    school_lookup_issues, school_mismatch_count, school_reference_count = (
        _detect_school_lookup_mismatches(
            insp_df,
            school_columns=school_name_columns,
            code_to_name_school=code_to_name_school,
            school_name_to_code=school_name_to_code,
            binding_policy=cfg.policy.mentor_school_binding,
        )
    )
    school_mismatch_ratio = (
        school_mismatch_count / school_reference_count if school_reference_count else 0.0
    )
    school_lookup_threshold = float(cfg.school_lookup_mismatch_threshold or 0.0)
    school_lookup_threshold_exceeded = (
        school_reference_count > 0 and school_mismatch_ratio > school_lookup_threshold
    )
    if school_mismatch_count:
        progress(
            12,
            (
                "school lookup mismatches="
                f"{school_mismatch_count} refs={school_reference_count}"
                f" ratio={school_mismatch_ratio:.1%}"
            ),
        )

    insp = insp_df.copy()

    if cfg.enable_capacity_gate:
        insp, removed_mentors, capacity_metrics, r0_skipped = capacity_gate(
            insp, cfg=cfg, progress=progress
        )
    else:
        removed_mentors = pd.DataFrame()
        capacity_metrics = CapacityGateMetrics.empty()
        r0_skipped = True
        progress(15, "capacity gate disabled by config")

    # detect columns
    gender_col = COL_GENDER if COL_GENDER in insp.columns else None
    included_col = next(
        (c for c in insp.columns if normalize_fa(c) == normalize_fa(COL_GROUP_INCLUDED)),
        next(
            (
                c
                for c in insp.columns
                if all(k in normalize_fa(c) for k in ("شامل", "گروه", "آزمایشی"))
            ),
            None,
        ),
    )
    group_cols = [c for c in insp.columns if ("گروه آزمایشی" in str(c)) and (c != included_col)]
    school_cols = [
        c for c in [COL_SCHOOL1, COL_SCHOOL2, COL_SCHOOL3, COL_SCHOOL4] if c in insp.columns
    ]

    # generate rows
    progress(30, "preparing vectorized base rows")
    insp_valid, invalid_mentors_df = _filter_invalid_mentors(
        insp,
        cfg=cfg,
        gender_col=gender_col,
        included_col=included_col,
        group_cols=group_cols,
    )
    invalid_school_indices: set[Any] = set()
    if school_lookup_issues.empty:
        school_lookup_invalid = pd.DataFrame(
            columns=[
                "row_index",
                "پشتیبان",
                "مدیر",
                "reason",
                "school_column",
                "school_value",
                "raw_school_value",
            ]
        )
    else:
        if "source_index" in school_lookup_issues.columns:
            invalid_school_indices = set(school_lookup_issues["source_index"].dropna().tolist())
            school_lookup_invalid = school_lookup_issues.drop(
                columns=["source_index"], errors="ignore"
            )
        else:
            school_lookup_invalid = school_lookup_issues
    if invalid_school_indices:
        insp_valid = insp_valid.drop(index=list(invalid_school_indices), errors="ignore")
    if invalid_mentors_df.empty:
        invalid_mentors_df = school_lookup_invalid.copy()
    elif not school_lookup_invalid.empty:
        invalid_mentors_df = pd.concat(
            [invalid_mentors_df, school_lookup_invalid], ignore_index=True, sort=False
        )

    if school_lookup_threshold_exceeded:
        message = (
            f"کد/نام مدرسه ناشناخته ({school_mismatch_count}) بیش از آستانهٔ مجاز "
            f"({school_lookup_threshold:.1%}) است؛ جزئیات در شیت invalid_mentors ثبت شد."
        )
        if cfg.fail_on_school_lookup_threshold:
            error = ValueError(message)
            setattr(error, "is_school_lookup_threshold_error", True)
            setattr(error, "school_lookup_mismatch_count", int(school_mismatch_count))
            setattr(error, "school_lookup_mismatch_ratio", float(school_mismatch_ratio))
            setattr(error, "invalid_mentors_df", invalid_mentors_df)
            raise error
        progress(12, f"⚠️ {message}")

    base_df, unseen_groups, unmatched_schools = _prepare_base_rows(
        insp_valid,
        cfg=cfg,
        name_to_code=name_to_code,
        code_to_name=code_to_name,
        buckets=buckets,
        synonyms=synonyms,
        school_name_to_code=school_name_to_code,
        code_to_name_school=code_to_name_school,
        group_cols=group_cols,
        school_cols=school_cols,
        gender_col=gender_col,
        included_col=included_col,
    )
    base_df = apply_mentor_pool_governance(
        base_df,
        cfg.policy.mentor_pool_governance,
    )
    if not school_lookup_invalid.empty and "raw_school_value" in school_lookup_invalid.columns:
        derived_unmatched = [
            {
                "raw_school": str(row.get("raw_school_value", "")),
                "supporter": row.get("پشتیبان", ""),
                "manager": row.get("مدیر", ""),
            }
            for row in school_lookup_invalid.to_dict("records")
        ]
        if derived_unmatched:
            unmatched_schools.extend(derived_unmatched)

    progress(55, "assembling matrix variants")
    cap_current_col = cfg.capacity_current_column or CAPACITY_CURRENT_COL
    cap_special_col = cfg.capacity_special_column or CAPACITY_SPECIAL_COL
    remaining_col = cfg.remaining_capacity_column or "remaining_capacity"
    school_code_col = cfg.school_code_column or COL_SCHOOL_CODE
    normal_df = _explode_rows(
        base_df.loc[base_df["can_normal"]],
        alias_col="alias_normal",
        status_col="statuses_normal",
        school_col="schools_normal",
        type_label="عادی",
        code_to_name_school=code_to_name_school,
        cfg=cfg,
        cap_current_col=cap_current_col,
        cap_special_col=cap_special_col,
        remaining_col=remaining_col,
        school_code_col=school_code_col,
    )
    school_df = _explode_rows(
        base_df.loc[base_df["can_school"]],
        alias_col="alias_school",
        status_col="statuses_school",
        school_col="school_codes",
        type_label="مدرسه‌ای",
        code_to_name_school=code_to_name_school,
        cfg=cfg,
        cap_current_col=cap_current_col,
        cap_special_col=cap_special_col,
        remaining_col=remaining_col,
        school_code_col=school_code_col,
    )

    matrix = pd.concat([normal_df, school_df], ignore_index=True, sort=False)
    finance_col = cfg.policy.stage_column("finance")
    center_col = cfg.policy.stage_column("center")

    if matrix.empty:
        matrix = pd.DataFrame(
            columns=[
                "جایگزین",
                "پشتیبان",
                "کد کارمندی پشتیبان",
                "مدیر",
                "ردیف پشتیبان",
                "نام رشته",
                "کدرشته",
                "جنسیت",
                "دانش آموز فارغ",
                center_col,
                finance_col,
                school_code_col,
                "عادی مدرسه",
                "mentor_school_binding_mode",
                "has_school_constraint",
                "نام مدرسه",
                "جنسیت2",
                "دانش آموز فارغ2",
                "مرکز گلستان صدرا3",
                cap_current_col,
                cap_special_col,
                remaining_col,
            ]
        )

    unseen_groups_df = (
        pd.DataFrame(unseen_groups).drop_duplicates() if unseen_groups else pd.DataFrame()
    )
    unmatched_schools_df = (
        pd.DataFrame(unmatched_schools).drop_duplicates() if unmatched_schools else pd.DataFrame()
    )
    invalid_group_token_count = len(unseen_groups_df)
    unmatched_school_count = len(unmatched_schools_df)

    dedup_threshold = float(cfg.dedup_removed_ratio_threshold or 0.0)
    rows_before_dedupe = len(matrix)
    rows_after_dedupe = len(matrix)
    dedup_removed_rows = 0
    dedup_removed_ratio = 0.0
    dedup_threshold_exceeded = False
    group_coverage_df = pd.DataFrame()
    group_coverage_summary: dict[str, int | float] = {}

    if not matrix.empty:
        matrix = matrix.copy()
        matrix["ردیف پشتیبان"] = ensure_series(matrix["ردیف پشتیبان"]).map(_coerce_int_like)
        school_series = ensure_series(matrix[school_code_col])
        matrix[school_code_col] = school_series.map(lambda v: safe_int_value(v, default=0)).astype(
            "int64"
        )
        matrix["کد کارمندی پشتیبان"] = (
            ensure_series(matrix["کد کارمندی پشتیبان"])
            .astype("string")
            .str.strip()
            .fillna("")
            .astype(object)
        )
        matrix["پشتیبان"] = (
            ensure_series(matrix["پشتیبان"]).astype("string").str.strip().fillna("").astype(object)
        )
        matrix["مدیر"] = (
            ensure_series(matrix["مدیر"]).astype("string").str.strip().fillna("").astype(object)
        )
        matrix["نام رشته"] = (
            ensure_series(matrix["نام رشته"]).astype("string").str.strip().fillna("").astype(object)
        )
        matrix["نام مدرسه"] = (
            ensure_series(matrix["نام مدرسه"]).astype("string").fillna("").astype(object)
        )
        matrix["عادی مدرسه"] = (
            ensure_series(matrix["عادی مدرسه"])
            .astype("string")
            .str.strip()
            .fillna("")
            .astype(object)
        )
        matrix["جایگزین"] = (
            ensure_series(matrix["جایگزین"]).astype("string").str.strip().fillna("").astype(object)
        )
        if finance_col in matrix.columns:
            matrix[finance_col] = ensure_series(matrix[finance_col]).astype("Int64")
        if center_col in matrix.columns:
            matrix[center_col] = ensure_series(matrix[center_col]).astype("int64")
        matrix["جنسیت"] = ensure_series(matrix["جنسیت"]).astype("Int64")
        matrix["دانش آموز فارغ"] = ensure_series(matrix["دانش آموز فارغ"]).astype("Int64")

        rows_before_dedupe = len(matrix)
        dedupe_cols = [col for col in DEDUP_KEY_ORDER if col in matrix.columns]
        if dedupe_cols:
            matrix = matrix.drop_duplicates(subset=dedupe_cols, keep="first")
        rows_after_dedupe = len(matrix)
        dedup_removed_rows = max(rows_before_dedupe - rows_after_dedupe, 0)
        dedup_removed_ratio = dedup_removed_rows / rows_before_dedupe if rows_before_dedupe else 0.0
        dedup_threshold_exceeded = rows_before_dedupe > 0 and (
            dedup_removed_ratio > dedup_threshold
        )
        progress(
            80,
            (
                "dedupe removed="
                f"{dedup_removed_rows} ratio={dedup_removed_ratio:.1%}"
                f" threshold={dedup_threshold:.1%}"
            ),
        )
        sort_cols = [col for col in SORT_COLUMNS if col in matrix.columns]
        if sort_cols:
            matrix = matrix.sort_values(sort_cols, kind="stable")

        _validate_finance_invariants(matrix, cfg=cfg, finance_col=finance_col)
        _validate_alias_contract(matrix, cfg=cfg)
        _validate_school_code_contract(matrix, school_code_col=school_code_col)

    coverage_policy = CoveragePolicyConfig(
        denominator_mode=cfg.policy.coverage_options.denominator_mode,
        require_student_presence=cfg.policy.coverage_options.require_student_presence,
        include_blocked_candidates_in_denominator=cfg.policy.coverage_options.include_blocked_candidates_in_denominator,
    )
    coverage_metrics, group_coverage_df, group_coverage_summary_raw = compute_coverage_metrics(
        matrix_df=matrix,
        base_df=base_df,
        students_df=None,
        join_keys=cfg.policy.join_keys,
        policy=coverage_policy,
        unmatched_school_count=unmatched_school_count,
        invalid_group_token_count=invalid_group_token_count,
        center_column=center_col,
        finance_column=finance_col,
        school_code_column=school_code_col,
    )
    group_coverage_summary = dict(group_coverage_summary_raw)
    group_coverage_summary = {
        **group_coverage_summary,
        "coverage_total_groups": coverage_metrics.total_groups,
        "coverage_covered_groups": coverage_metrics.covered_groups,
        "coverage_unseen_viable_groups": coverage_metrics.unseen_viable_groups,
        "coverage_invalid_group_token_count": coverage_metrics.invalid_group_token_count,
    }
    _append_progress_row(
        {
            "step": "group_coverage_debug",
            "pct": 92,
            "message": (
                "group coverage computed: "
                f"total={group_coverage_summary.get('total_groups', 0)} "
                f"covered={group_coverage_summary.get('covered_groups', 0)} "
                f"candidate_only={group_coverage_summary.get('candidate_only_groups', 0)} "
                f"blocked={group_coverage_summary.get('blocked_candidate_groups', 0)}"
            ),
            "groups_total": int(group_coverage_summary.get("total_groups", 0)),
            "groups_covered": int(group_coverage_summary.get("covered_groups", 0)),
            "groups_candidate_only": int(group_coverage_summary.get("candidate_only_groups", 0)),
            "groups_blocked_candidate": int(
                group_coverage_summary.get("blocked_candidate_groups", 0)
            ),
            "groups_matrix_only": int(group_coverage_summary.get("matrix_only_groups", 0)),
            "coverage_total_groups": coverage_metrics.total_groups,
            "coverage_covered_groups": coverage_metrics.covered_groups,
            "coverage_unseen_viable_groups": coverage_metrics.unseen_viable_groups,
            "coverage_invalid_group_token_count": coverage_metrics.invalid_group_token_count,
        }
    )
    progress(
        92,
        (
            "group coverage: "
            f"total={group_coverage_summary.get('total_groups', 0)} "
            f"covered={group_coverage_summary.get('covered_groups', 0)} "
            f"candidate_only={group_coverage_summary.get('candidate_only_groups', 0)} "
            f"blocked={group_coverage_summary.get('blocked_candidate_groups', 0)} "
            f"coverage_total={coverage_metrics.total_groups} "
            f"coverage_unseen={coverage_metrics.unseen_viable_groups}"
        ),
    )

    total_rows = len(matrix)
    matrix.insert(0, "counter", range(1, total_rows + 1))

    nodup = matrix.drop(columns=["counter"]).drop_duplicates()
    if len(matrix) != len(nodup):
        raise AssertionError("Duplicate rows before counter!")

    coverage_ratio = coverage_metrics.coverage_ratio
    min_coverage_ratio = float(cfg.min_coverage_ratio or 0.0)
    coverage_validation_fields = build_coverage_validation_fields(
        metrics=coverage_metrics,
        coverage_threshold=min_coverage_ratio,
        total_rows=total_rows,
    )

    duplicate_threshold = int(cfg.join_key_duplicate_threshold or 0)
    base_row = {
        "policy_version": cfg.policy_version,
        "policy_version_expected": cfg.expected_policy_version or pd.NA,
        "total_rows": total_rows,
        "distinct_supporters": matrix["پشتیبان"].nunique() if not matrix.empty else 0,
        "school_based_rows": (
            int((matrix["عادی مدرسه"] == "مدرسه‌ای").sum()) if not matrix.empty else 0
        ),
        "finance_0_rows": (
            int((matrix[finance_col] == Finance.NORMAL).sum()) if not matrix.empty else 0
        ),
        "finance_1_rows": (
            int((matrix[finance_col] == Finance.BONYAD).sum()) if not matrix.empty else 0
        ),
        "finance_3_rows": (
            int((matrix[finance_col] == Finance.HEKMAT).sum()) if not matrix.empty else 0
        ),
        "removed_mentors": 0 if removed_mentors is None else len(removed_mentors),
        "capacity_removed_total": capacity_metrics.total_removed,
        "capacity_special_capacity_lost": capacity_metrics.total_special_capacity_lost,
        "capacity_percent_pool_kept": capacity_metrics.percent_pool_kept,
        "r0_skipped": 1 if r0_skipped else 0,
        "group_coverage_total": int(group_coverage_summary.get("total_groups", 0)),
        "group_coverage_covered": int(group_coverage_summary.get("covered_groups", 0)),
        "group_coverage_candidate_only": int(
            group_coverage_summary.get("candidate_only_groups", 0)
        ),
        "group_coverage_blocked": int(group_coverage_summary.get("blocked_candidate_groups", 0)),
        "group_coverage_matrix_only": int(group_coverage_summary.get("matrix_only_groups", 0)),
        "school_lookup_mismatch_count": int(school_mismatch_count),
        "school_lookup_mismatch_refs": int(school_reference_count),
        "school_lookup_mismatch_ratio": float(school_mismatch_ratio),
        "school_lookup_mismatch_threshold": float(school_lookup_threshold),
        "join_key_duplicate_rows": int(len(duplicate_join_keys_df)),
        "join_key_duplicate_threshold": duplicate_threshold,
        "dedup_removed_rows": int(dedup_removed_rows),
        "dedup_removed_ratio": dedup_removed_ratio,
        "dedup_removed_threshold": dedup_threshold,
        "alias_autofill": alias_autofill,
        "alias_unmatched": alias_unmatched,
        "warning_type": pd.NA,
        "warning_message": pd.NA,
        "warning_payload": pd.NA,
    }
    base_row.update(coverage_validation_fields)
    duplicate_warning_rows = _build_duplicate_warning_rows(
        duplicate_summary,
        join_keys=cfg.policy.join_keys,
        mentor_column=COL_MENTOR_ID,
    )
    validation_rows = [base_row]
    validation_columns = list(base_row.keys())
    for warning in duplicate_warning_rows:
        warning_row = {column: pd.NA for column in validation_columns}
        warning_row.update(warning)
        validation_rows.append(warning_row)
    validation = pd.DataFrame(validation_rows, columns=validation_columns)

    _append_progress_row(
        {
            "step": "deduplicate_matrix",
            "pct": 80,
            "message": "drop_duplicates applied on final matrix",
            "total_rows_before_dedup": rows_before_dedupe,
            "total_rows_after_dedup": rows_after_dedupe,
            "dedup_removed_rows": int(dedup_removed_rows),
            "dedup_removed_ratio": dedup_removed_ratio,
            "dedup_removed_threshold": dedup_threshold,
            "status": "error" if dedup_threshold_exceeded else "ok",
            "dataset": MATRIX_MODE,
        }
    )

    progress_log = pd.DataFrame(progress_rows)
    progress_log.attrs["column_normalization_reports"] = normalization_meta
    progress_log.attrs["group_coverage"] = group_coverage_df
    progress_log.attrs["group_coverage_summary"] = group_coverage_summary
    progress_log.attrs["coverage_metrics"] = coverage_metrics

    removed_df = removed_mentors
    progress(90, "matrix assembly complete")
    progress(
        95,
        (
            "coverage ratio "
            f"{coverage_ratio:.1%} (covered_groups={coverage_metrics.covered_groups}"
            f", total_groups={coverage_metrics.total_groups}"
            f", unseen_groups={coverage_metrics.unseen_viable_groups}"
            f", invalid_tokens={coverage_metrics.invalid_group_token_count}"
            f", unmatched_schools={unmatched_school_count})"
        ),
    )

    if dedup_threshold_exceeded:
        message = (
            f"حذف رکوردهای تکراری ({dedup_removed_ratio:.1%}) از آستانهٔ مجاز "
            f"({dedup_threshold:.1%}) بیشتر است."
        )
        LOGGER.error(
            "dedupe threshold exceeded: removed=%s threshold=%s rows_before=%s rows_after=%s",
            f"{dedup_removed_ratio:.4f}",
            f"{dedup_threshold:.4f}",
            rows_before_dedupe,
            rows_after_dedupe,
        )
        progress(
            85,
            (
                "⚠️ dedupe threshold exceeded: removed="
                f"{dedup_removed_rows} ratio={dedup_removed_ratio:.1%}"
            ),
        )
        error = ValueError(message)
        setattr(error, "is_dedup_removed_threshold_error", True)
        setattr(error, "dedup_removed_rows", int(dedup_removed_rows))
        setattr(error, "dedup_removed_ratio", float(dedup_removed_ratio))
        raise error

    unseen_preview: list[dict[str, object]] | None = None
    coverage_gate_unseen = coverage_metrics.unseen_viable_groups
    if (
        coverage_metrics.total_groups
        and coverage_ratio < min_coverage_ratio
        and coverage_gate_unseen > 0
    ):
        if (
            isinstance(group_coverage_df, pd.DataFrame)
            and not group_coverage_df.empty
            and "is_unseen_viable" in group_coverage_df.columns
        ):
            unseen_preview = (
                group_coverage_df.loc[group_coverage_df["is_unseen_viable"], cfg.policy.join_keys]
                .head(5)
                .to_dict(orient="records")
            )
        message = (
            f"نسبت پوشش خروجی {coverage_ratio:.1%} کمتر از حداقل مجاز "
            f"{min_coverage_ratio:.1%} است؛ unmatched_schools={unmatched_school_count}، "
            f"unseen_groups={coverage_gate_unseen}."
        )
        error = ValueError(message)
        setattr(error, "is_coverage_threshold_error", True)
        setattr(error, "coverage_unseen_preview", unseen_preview)
        raise error

    return (
        matrix,
        validation,
        removed_df,
        unmatched_schools_df,
        unseen_groups_df,
        invalid_mentors_df,
        duplicate_join_keys_df,
        progress_log,
    )


# =============================================================================
# VALIDATION vs StudentReport (optional)
# =============================================================================
def infer_students_gender_from_hint(source: str | None) -> int | None:
    s = str(source or "")
    if "3570" in s:
        return Gender.MALE
    if "3730" in s:
        return Gender.FEMALE
    return None


def resolve_students_gender_series(
    stud_df: pd.DataFrame,
    *,
    source_hint: str | None = None,
    mode: str = "auto",
) -> pd.Series:
    mode = (mode or "auto").lower()
    n = len(stud_df)
    if mode == "male":
        return pd.Series([Gender.MALE] * n, index=stud_df.index)
    if mode == "female":
        return pd.Series([Gender.FEMALE] * n, index=stud_df.index)
    hint = infer_students_gender_from_hint(source_hint)
    if hint is not None:
        return pd.Series([hint] * n, index=stud_df.index)
    if "جنسیت" in stud_df.columns:
        return stud_df["جنسیت"].apply(norm_gender).fillna(Gender.MALE)
    return pd.Series([Gender.MALE] * n, index=stud_df.index)


def validate_with_students(
    students_df: pd.DataFrame,
    matrix_df: pd.DataFrame,
    schools_df: pd.DataFrame,
    crosswalk_groups_df: pd.DataFrame,
    *,
    crosswalk_synonyms_df: pd.DataFrame | None = None,
    students_gender_mode: str = "auto",
    students_source_hint: str | None = None,
    cfg: BuildConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
    cfg = cfg or BuildConfig()
    school_code_col = cfg.school_code_column or COL_SCHOOL_CODE
    center_col = cfg.policy.stage_column("center")

    stud_raw = students_df.copy()
    stud_raw.columns = [normalize_header(col) for col in stud_raw.columns]
    schools = schools_df.copy()
    _, school_name_to_code = build_school_maps(schools, cfg=cfg)
    name_to_code, _, _, _ = prepare_crosswalk_mappings(
        crosswalk_groups_df,
        crosswalk_synonyms_df,
    )

    # Support "کد پستی" OR "کد جایگزین"
    std_alias_col = (
        "کد پستی"
        if "کد پستی" in stud_raw.columns
        else ("کد جایگزین" if "کد جایگزین" in stud_raw.columns else None)
    )
    if std_alias_col is None:
        raise ValueError("در StudentReport ستونی با عنوان «کد پستی» یا «کد جایگزین» یافت نشد.")

    postal_series = stud_raw[std_alias_col].apply(to_numlike_str)
    resolution_frame = stud_raw.copy()
    resolution_frame["student_postal"] = postal_series

    group_stats: dict[str, int] = {}
    group_codes = resolution_frame.apply(
        lambda row: resolve_group_code(
            row,
            name_to_code,
            major_column="کد رشته",
            group_column="گروه آزمایشی",
            prefer_major_code=bool(cfg.prefer_major_code),
            stats=group_stats,
            logger=LOGGER,
        ),
        axis=1,
    )

    school_code_series = None
    school_column = cfg.policy.columns.school_code
    if school_column in stud_raw.columns:
        school_code_series = stud_raw[school_column]

    if school_code_series is None and COL_SCHOOL1 in stud_raw.columns:
        school_code_series = stud_raw[COL_SCHOOL1].apply(
            lambda x: school_name_to_code.get(normalize_fa(x), "")
        )

    stud = pd.DataFrame(
        {
            "student_postal": postal_series,
            "alias_norm": postal_series,
            "mentor_name": ensure_series(stud_raw["نام پشتیبان"]).astype(str).str.strip(),
            "manager": ensure_series(stud_raw["مدیر"]).astype(str).str.strip(),
            "school_code": school_code_series if school_code_series is not None else "",
        }
    )
    stud["group_code"] = pd.Series(pd.array(group_codes, dtype="Int64"), index=stud.index)
    stud["status_code"] = Status.STUDENT
    stud["gender_code"] = resolve_students_gender_series(
        stud_raw,
        source_hint=students_source_hint,
        mode=students_gender_mode,
    ).values

    LOGGER.info(
        "student group_code resolution (prefer_major_code=%s): "
        "major=%d, crosswalk=%d, mismatch=%d, unresolved=%d",
        cfg.prefer_major_code,
        group_stats.get("resolved_by_major_code", 0),
        group_stats.get("resolved_by_crosswalk", 0),
        group_stats.get("mismatch_major_vs_group", 0),
        group_stats.get("unresolved_group_code", 0),
    )

    mat = matrix_df.copy()
    mat["alias_norm"] = ensure_series(mat["جایگزین"]).apply(to_numlike_str)
    mat["school_code"] = ensure_series(mat[school_code_col]).astype(str).str.strip()

    status_column = cfg.policy.stage_column("graduation_status")
    school_column = cfg.policy.columns.school_code
    stud["student_binding"] = stud.apply(
        lambda row: classify_student_binding(
            {status_column: row["status_code"], school_column: row["school_code"]}, cfg=cfg
        ),
        axis=1,
    )

    def _sub_by_type(row: pd.Series) -> tuple[pd.DataFrame, str | None]:
        binding = row["student_binding"]
        if binding is StudentBindingKind.NORMAL:
            sub = mat[(mat["عادی مدرسه"] == "عادی") & (mat["alias_norm"] == row["alias_norm"])]
            if not sub.empty:
                return (sub, None)
            if row["school_code"]:
                school_sub = mat[(mat["عادی مدرسه"] == "مدرسه‌ای")]
                school_sub = school_sub[
                    school_sub["school_code"].astype(str) == str(row["school_code"])
                ]
                return (school_sub, None if not school_sub.empty else "no school-code match")
            return (sub, "no normal alias match")
        if binding is StudentBindingKind.SCHOOL:
            sub = mat[(mat["عادی مدرسه"] == "مدرسه‌ای")]
            if row["school_code"]:
                sub = sub[sub["school_code"].astype(str) == str(row["school_code"])]
            return (sub, None if not sub.empty else "no school-code match")
        return (mat.iloc[0:0], "legacy binding kind")

    def _check_gender(row: pd.Series, sub: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
        sub2 = sub[sub["جنسیت"] == row["gender_code"]]
        return (sub2, None if not sub2.empty else "gender mismatch")

    def _check_status(row: pd.Series, sub: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
        sub2 = sub[sub["دانش آموز فارغ"] == row["status_code"]]
        return (sub2, None if not sub2.empty else "status mismatch")

    def _check_center(row: pd.Series, sub: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
        expected = domain_center_from_manager(row["manager"], cfg=cfg)
        sub2 = sub[sub[center_col] == expected]
        return (sub2, None if not sub2.empty else "center mismatch (manager-based)")

    def _check_group(row: pd.Series, sub: pd.DataFrame) -> tuple[pd.DataFrame, str | None]:
        value = row.get("group_code")
        if value is None or (pd.isna(value)):
            return (sub, "دانش‌آموز فاقد «کد رشته» و «گروه آزمایشی» معتبر است")
        group_col = cfg.policy.join_keys[0]
        sub2 = sub[sub[group_col] == int(value)]
        return (sub2, None if not sub2.empty else "group_code mismatch")

    def first_fail_reason(row: pd.Series) -> str:
        sub, err = _sub_by_type(row)
        if err:
            return err
        for checker in (_check_gender, _check_status, _check_center, _check_group):
            sub, err = checker(row, sub)
            if err:
                return err
        return "MATCHED"

    stud["reason"] = stud.apply(first_fail_reason, axis=1)
    stud["match"] = stud["reason"].eq("MATCHED")

    breakdown = stud["reason"].value_counts().reset_index()
    breakdown.columns = ["reason", "count"]
    summary = {
        "total": int(len(stud)),
        "matched": int(stud["match"].sum()),
        "unmatched": int((~stud["match"]).sum()),
    }

    return stud, breakdown, summary


# =============================================================================
# DEDUPE KEYS
# =============================================================================
DEDUP_KEY_ORDER = [
    "جایگزین",
    "پشتیبان",
    "کد کارمندی پشتیبان",
    "مدیر",
    "نام رشته",
    "کدرشته",
    "جنسیت",
    "دانش آموز فارغ",
    "مرکز گلستان صدرا",
    "مالی حکمت بنیاد",
    "کد مدرسه",
    "عادی مدرسه",
]

SORT_COLUMNS = ["مرکز گلستان صدرا", "کدرشته", "کد مدرسه", "جایگزین"]
