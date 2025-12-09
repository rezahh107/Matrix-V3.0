"""تعریف قراردادهای دادهٔ حوزهٔ Eligibility Matrix (Core-only, بدون I/O).

این ماژول صرفاً تایپ‌ها را نگه می‌دارد و منطق ندارد. نگاشت کلیدهای join به
کمک :class:`JoinKeyValues` در قالب ساختار فقط‌خواندنی و با اجبار «۶ مقدار عددی»
ذخیره می‌شود تا خطاهای داده‌ای به‌سرعت شناسایی شوند.

مثال:
    >>> from app.core.common.types import JoinKeyValues
    >>> keys = JoinKeyValues({
    ...   "کدرشته": 1,
    ...   "گروه_آزمایشی": 1,
    ...   "جنسیت": 1,
    ...   "دانش_آموز_فارغ": 0,
    ...   "مرکز_گلستان_صدرا": 1,
    ...   "مالی_حکمت_بنیاد": 0,
    ... })
    >>> keys["کدرشته"]
    1
"""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import (
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    Mapping,
    MutableMapping,
    ValuesView,
)
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final, Literal, NewType, TypedDict, TypeGuard, cast

import pandas as pd

from .columns import CANON_EN_TO_FA

_NUM = re.compile(r"(\d+)")

HeaderMode = Literal["fa", "en", "fa_en"]
TraceStageName = Literal[
    "type",
    "group",
    "gender",
    "graduation_status",
    "center",
    "finance",
    "school",
    "capacity_gate",
]
TraceStageLiteral = TraceStageName
TraceStageFlags = dict[TraceStageName, bool]

CANONICAL_TRACE_ORDER: tuple[TraceStageName, ...] = (
    "type",
    "group",
    "gender",
    "graduation_status",
    "center",
    "finance",
    "school",
    "capacity_gate",
)

TRACE_STAGE_NAME_SET: frozenset[TraceStageName] = frozenset(CANONICAL_TRACE_ORDER)


def _underscore_key(value: str) -> str:
    """بازگرداندن نام کلید با جداکنندهٔ «_» برای استفادهٔ داخلی.

    شکل‌های حاوی فاصلهٔ معمول در Policy/SSoT را به فرم پایدار با
    ``_`` تبدیل می‌کند تا نسخهٔ داخلی کلیدهای join با تست‌ها و
    سایر بخش‌های سیستم همسو باشد.
    """

    spaced = re.sub(r"\s+", " ", value.strip())
    return spaced.replace(" ", "_")


JOIN_KEY_GROUP: Final[str] = _underscore_key(CANON_EN_TO_FA["group_code"])
JOIN_KEY_GENDER: Final[str] = _underscore_key(CANON_EN_TO_FA["gender"])
JOIN_KEY_GRADUATION: Final[str] = _underscore_key(CANON_EN_TO_FA["graduation_status"])
JOIN_KEY_CENTER: Final[str] = _underscore_key(CANON_EN_TO_FA["center"])
JOIN_KEY_FINANCE: Final[str] = _underscore_key(CANON_EN_TO_FA["finance"])
JOIN_KEY_SCHOOL_CODE: Final[str] = _underscore_key(CANON_EN_TO_FA["school_code"])

JoinKeyValueMapping = Mapping[str, int]

CANONICAL_JOIN_KEYS: tuple[str, ...] = (
    JOIN_KEY_GROUP,
    JOIN_KEY_GENDER,
    JOIN_KEY_GRADUATION,
    JOIN_KEY_CENTER,
    JOIN_KEY_FINANCE,
    JOIN_KEY_SCHOOL_CODE,
)

JoinKeyName = NewType("JoinKeyName", str)

JoinProfile = Mapping[JoinKeyName, int]


JoinKeyEntityType = Literal["student", "mentor", "school", "form"]


@dataclass(frozen=True)
class JoinKeyValidationIssue:
    """Structured validation issue captured during join-key canonicalization."""

    entity_type: JoinKeyEntityType
    row_index: int
    column: str
    raw_value: object
    error_code: str


@dataclass(frozen=True)
class JoinKeyValidationResult:
    """Result of validating and canonicalizing join keys for a DataFrame."""

    canonical_df: pd.DataFrame
    issues: list[JoinKeyValidationIssue]

    @property
    def invalid_rows(self) -> pd.DataFrame:
        """Return a DataFrame representation of all validation issues."""

        if not self.issues:
            return pd.DataFrame(
                columns=["entity_type", "row_index", "column", "raw_value", "error_code"]
            )
        return pd.DataFrame(
            [
                {
                    "entity_type": issue.entity_type,
                    "row_index": issue.row_index,
                    "column": issue.column,
                    "raw_value": issue.raw_value,
                    "error_code": issue.error_code,
                }
                for issue in self.issues
            ]
        )


@dataclass(frozen=True)
class StudentDomainValidationIssue:
    """Structured issue raised during student domain validation."""

    row_index: int
    group_code: int | None
    graduation_status: int | None
    allowed_statuses: tuple[int, ...]
    error_code: str
    severity: str = "P1"


@dataclass(frozen=True)
class StudentDomainValidationResult:
    """Result of validating domain-specific student invariants."""

    canonical_df: pd.DataFrame
    issues: list[StudentDomainValidationIssue]

    @property
    def issues_df(self) -> pd.DataFrame:
        if not self.issues:
            return pd.DataFrame(
                columns=[
                    "row_index",
                    "group_code",
                    "graduation_status",
                    "allowed_statuses",
                    "error_code",
                ]
            )
        return pd.DataFrame(
            [
                {
                    "row_index": issue.row_index,
                    "group_code": issue.group_code,
                    "graduation_status": issue.graduation_status,
                    "allowed_statuses": issue.allowed_statuses,
                    "error_code": issue.error_code,
                    "severity": issue.severity,
                }
                for issue in self.issues
            ]
        )

    @property
    def can_continue(self) -> bool:
        return not any(issue.severity == "P0" for issue in self.issues)


@dataclass(frozen=True)
class StudentValidationBundle:
    """Aggregate result for student import validation layers."""

    join_keys: JoinKeyValidationResult
    domain: StudentDomainValidationResult

    @property
    def canonical_df(self) -> pd.DataFrame:
        return self.domain.canonical_df


PolicyGender = Literal["male", "female"]
GraduationStatus = Literal["graduated", "not_graduated"]
CenterStatus = Literal["registered", "not_registered"]


def parse_header_mode(value: object) -> HeaderMode:
    """Normalize and validate header mode values.

    Args:
        value: ورودی خام که باید یکی از ``"fa"``, ``"en"`` یا ``"fa_en"`` باشد.

    Raises:
        ValueError: اگر مقدار ورودی معتبر نباشد یا از نوع رشته نباشد.
    """

    if not isinstance(value, str):
        raise ValueError("Header mode must be a string")
    normalized = value.strip()
    if normalized not in {"fa", "en", "fa_en"}:
        raise ValueError(f"Unsupported header_mode '{value}'")
    return cast(HeaderMode, normalized)


def is_trace_stage_name(value: str) -> TypeGuard[TraceStageName]:
    """Type guard to check canonical trace stage names."""

    return value in TRACE_STAGE_NAME_SET


def ensure_trace_stage_name(value: str) -> TraceStageName:
    """Validate and cast a raw string to :data:`TraceStageName`."""

    if not is_trace_stage_name(value):
        raise ValueError(f"Invalid trace stage name: {value}")
    return value


def natural_key(s: str) -> tuple[object, ...]:
    """کلید طبیعی برای sort پایدار شناسه‌ها (EMP-2 قبل از EMP-10).

    مثال::

        >>> natural_key("EMP-2") < natural_key("EMP-10")
        True
    """

    text = str(s or "").strip()
    if not text:
        return ("",)

    parts: list[object] = []
    for token in _NUM.split(text):
        if not token:
            continue
        if token.isdecimal():
            parts.append(int(token))
        else:
            parts.append(token.lower())

    if not parts:
        return ("",)
    if not isinstance(parts[0], str):
        parts.insert(0, "")
    return tuple(parts)


def _normalize_join_key(key: str) -> str:
    normalized = key.replace("_", " ").strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _canonical_join_key_display(key: str, *, allow_unknown: bool = False) -> str:
    normalized = _normalize_join_key(key)
    canonical_map = {_normalize_join_key(value): value for value in CANONICAL_JOIN_KEYS}
    if normalized in canonical_map:
        return canonical_map[normalized]

    english_to_fa = {
        _normalize_join_key(en_key): _underscore_key(fa_value)
        for en_key, fa_value in CANON_EN_TO_FA.items()
    }
    if normalized in english_to_fa:
        return english_to_fa[normalized]

    spaced_variants = {
        _normalize_join_key(key.replace("_", " ")): key for key in CANONICAL_JOIN_KEYS
    }
    if normalized in spaced_variants:
        return spaced_variants[normalized]

    if allow_unknown:
        return str(key)
    raise ValueError(f"Unknown join key: {key}")


class JoinKeyValues(Mapping[str, int]):
    """نگهدارندهٔ فقط‌خواندنی برای ۶ کلید join به‌صورت اعداد صحیح.

    این کلاس ترتیب درج و نام‌های قراردادی «کدرشته»، «جنسیت»،
    «دانش آموز فارغ»، «مرکز گلستان صدرا»، «مالی حکمت بنیاد» و «کد مدرسه» را
    حفظ می‌کند و برای ساخت کلید ترکیبی (tuple یا dict) بدون نشتی ``Any``
    استفاده می‌شود.

    مثال کوتاه::

        >>> keys = JoinKeyValues({
        ...     "کدرشته": 1,
        ...     "جنسیت": 1,
        ...     "دانش آموز فارغ": 0,
        ...     "مرکز گلستان صدرا": 1,
        ...     "مالی حکمت بنیاد": 0,
        ...     "کد مدرسه": 10,
        ... })
        >>> keys["کدرشته"]
        1
    """

    __slots__ = ("_items", "_mapping", "_lookup_map")

    _items: tuple[tuple[str, int], ...]
    _mapping: Mapping[str, int]
    _lookup_map: Mapping[str, str]

    _EXPECTED_SENTINEL: Any = object()

    def __init__(
        self,
        data: Mapping[str, int] | MutableMapping[str, int],
        *,
        expected_keys: Iterable[str] | None | Any = _EXPECTED_SENTINEL,
    ):
        normalized_items: OrderedDict[str, int] = OrderedDict()
        for key, value in data.items():
            display_key = _canonical_join_key_display(str(key), allow_unknown=True)
            if not isinstance(value, int):
                raise TypeError(f"Join key '{display_key}' must be int")
            normalized_items[display_key] = value

        default_expected = expected_keys is JoinKeyValues._EXPECTED_SENTINEL
        display_expected = (
            CANONICAL_JOIN_KEYS
            if default_expected
            else tuple(expected_keys) if expected_keys else None
        )

        if len(normalized_items) != len(CANONICAL_JOIN_KEYS):
            raise ValueError("JoinKeyValues must contain exactly six entries")

        if display_expected is not None:
            display_keys = tuple(
                _canonical_join_key_display(str(key), allow_unknown=True)
                for key in display_expected
            )
            expected_set = {_normalize_join_key(key) for key in display_keys}
            data_set = {_normalize_join_key(key) for key in normalized_items}
            missing = tuple(key for key in display_keys if _normalize_join_key(key) not in data_set)
            extra = tuple(
                key for key in normalized_items if _normalize_join_key(key) not in expected_set
            )
            if missing or extra:
                raise ValueError("JoinKeyValues keys mismatch; " f"missing={missing} extra={extra}")
            if (not default_expected) and tuple(
                _normalize_join_key(key) for key in display_keys
            ) != tuple(_normalize_join_key(key) for key in normalized_items):
                raise ValueError(
                    "JoinKeyValues keys mismatch; ordering differs from provided expected_keys"
                )
            ordered = OrderedDict(
                (display_key, normalized_items[display_key]) for display_key in display_keys
            )
        else:
            ordered = OrderedDict(normalized_items)

        english_lookup = {
            _normalize_join_key(en_key): _canonical_join_key_display(
                display_key, allow_unknown=True
            )
            for en_key, display_key in CANON_EN_TO_FA.items()
            if _canonical_join_key_display(display_key, allow_unknown=True) in ordered
        }
        lookup_map = {
            **{_normalize_join_key(key): key for key in ordered},
            **{_normalize_join_key(key.replace("_", " ")): key for key in ordered},
            **english_lookup,
        }

        object.__setattr__(self, "_items", tuple(ordered.items()))
        object.__setattr__(self, "_mapping", MappingProxyType(dict(ordered)))
        object.__setattr__(self, "_lookup_map", MappingProxyType(lookup_map))

    def __setattr__(
        self, name: str, value: object
    ) -> None:  # pragma: no cover - immutability guard
        raise AttributeError("JoinKeyValues is immutable")

    def __delattr__(self, name: str) -> None:  # pragma: no cover - immutability guard
        raise AttributeError("JoinKeyValues is immutable")

    def __getitem__(self, key: str) -> int:  # pragma: no cover - Mapping API
        """دسترسی مستقیم به مقدار هر کلید join (همیشه ``int``)."""

        normalized = _normalize_join_key(str(key))
        display_key = self._lookup_map.get(normalized)
        if display_key is None:
            fallback = _canonical_join_key_display(str(key), allow_unknown=True)
            if fallback in self._mapping:
                return self._mapping[fallback]
            raise KeyError(key)
        return self._mapping[display_key]

    def __iter__(self) -> Iterator[str]:  # pragma: no cover - Mapping API
        """تکرار کلیدها با حفظ ترتیب قراردادی."""

        return iter(self._mapping)

    def __len__(self) -> int:  # pragma: no cover - Mapping API
        """تعداد کلیدها که همواره ۶ است."""

        return len(self._items)

    def __contains__(self, key: object) -> bool:  # pragma: no cover - Mapping API
        """بررسی وجود کلید با احترام به نوع ``str`` و ترتیب اصلی."""

        return isinstance(key, str) and _normalize_join_key(key) in self._lookup_map

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"JoinKeyValues({dict(self._items)!r})"

    def keys(self) -> KeysView[str]:
        """دسترسی به کلیدها با حفظ ترتیب درج."""

        return self._mapping.keys()

    def items(self) -> ItemsView[str, int]:
        """برگشت زوج‌های (کلید، مقدار) به‌ترتیب Policy."""

        return self._mapping.items()

    def values(self) -> ValuesView[int]:
        """مقادیر کلیدها به‌ترتیب درج."""

        return self._mapping.values()

    def as_dict(self) -> dict[str, int]:
        """کپی معمولی دیکشنری برای سازگاری با pandas/JSON."""

        return dict(self._items)

    @classmethod
    def from_policy(
        cls, data: Mapping[str, int | str | float | bool], join_keys: Iterable[str]
    ) -> JoinKeyValues:
        """ساخت نمونه از روی Policy با اجبار ترتیب کلیدها و تبدیل به int.

        Args:
            data: نگاشت ورودی شامل مقادیر کلیدها (قابل تبدیل به int نظیر str/float).
            join_keys: ترتیب دقیق کلیدها که باید ۶ تایی باشد.

        Raises:
            ValueError: اگر هر کلید موردانتظار در داده وجود نداشته باشد.
            TypeError: اگر تبدیل مقدار به int شکست بخورد.
        """

        expected_keys = tuple(str(key) for key in join_keys)
        ordered: OrderedDict[str, int] = OrderedDict()
        sentinel: object = object()
        for key in expected_keys:
            display_key = _canonical_join_key_display(key, allow_unknown=True)
            raw_value = data.get(key, sentinel)
            if raw_value is sentinel and display_key != key:
                raw_value = data.get(display_key, sentinel)
            if raw_value is sentinel:
                spaced_variant = display_key.replace("_", " ")
                raw_value = data.get(spaced_variant, sentinel)
            if raw_value is sentinel:
                raise ValueError(f"join key values missing for: {key}")
            try:
                coerced = int(cast(int | str | float | bool, raw_value))
            except (TypeError, ValueError):
                raise TypeError(f"Join key '{key}' must be int-convertible")
            ordered[display_key] = coerced

        return cls(ordered, expected_keys=expected_keys)


# سازگاری نامی با نسخه‌های قبلی
JoinKeys = JoinKeyValues
JoinKeysDF = JoinKeyValues

__all__ = [
    "natural_key",
    "HeaderMode",
    "TraceStageName",
    "TraceStageFlags",
    "TraceStageLiteral",
    "ensure_trace_stage_name",
    "parse_header_mode",
    "PolicyGender",
    "GraduationStatus",
    "CenterStatus",
    "CANONICAL_JOIN_KEYS",
    "JoinKeyValues",
    "JoinKeys",
    "JoinKeysDF",
    "JoinKeyValueMapping",
    "StudentRow",
    "MentorRow",
    "AllocationErrorLiteral",
    "AllocationAlertRecord",
    "MentorStateSnapshot",
    "MentorStateDelta",
    "AllocationLogRecord",
    "TraceStageRecord",
    "CANONICAL_TRACE_ORDER",
]


class StudentRow(TypedDict, total=False):
    """نمایندهٔ یک ردیف دانش‌آموز پس از نرمال‌سازی."""

    student_id: str
    کدرشته: int
    جنسیت: int
    دانش_آموز_فارغ: int
    مرکز_گلستان_صدرا: int
    مالی_حکمت_بنیاد: int
    کد_مدرسه: int
    گروه_آزمایشی: str
    نام: str


class MentorRow(TypedDict, total=False):
    """اطلاعات پشتیبان برای تخصیص ظرفیت و ردیابی."""

    پشتیبان: str
    کد_کارمندی_پشتیبان: str
    occupancy_ratio: float
    allocations_new: int
    remaining_capacity: int
    covered_now: int
    special_limit: int


class MentorStateSnapshot(TypedDict):
    """وضعیت خلاصه‌شدهٔ ظرفیت یک پشتیبان برای ثبت در Trace.

    مثال::

        >>> MentorStateSnapshot(remaining=3, alloc_new=1, occupancy_ratio=0.5)
    """

    remaining: int
    alloc_new: int
    occupancy_ratio: float


class MentorStateDelta(TypedDict):
    """تغییرات وضعیت پشتیبان قبل و بعد از تخصیص.

    مثال::

        >>> MentorStateDelta(
        ...     before=MentorStateSnapshot(remaining=2, alloc_new=0, occupancy_ratio=0.0),
        ...     after=MentorStateSnapshot(remaining=1, alloc_new=1, occupancy_ratio=0.5),
        ...     diff=MentorStateSnapshot(remaining=-1, alloc_new=1, occupancy_ratio=0.5),
        ... )
    """

    before: MentorStateSnapshot
    after: MentorStateSnapshot
    diff: MentorStateSnapshot


AllocationErrorLiteral = Literal[
    "ELIGIBILITY_NO_MATCH",
    "CAPACITY_FULL",
    "DATA_MISSING",
    "INTERNAL_ERROR",
    "CAPACITY_UNDERFLOW",
]


class AllocationAlertRecord(TypedDict, total=False):
    """هشدار ساخت‌یافته برای گزارش مرحلهٔ حذف کاندید."""

    code: str
    stage: str
    message: str
    context: dict[str, Any]


class AllocationLogRecord(TypedDict, total=False):
    """ساختار استاندارد برای ثبت Trace تصمیمات تخصیص."""

    row_index: int
    student_id: str
    allocation_status: Literal["success", "failed"]
    mentor_selected: str | None
    mentor_id: str | None
    occupancy_ratio: float | None
    join_keys: JoinKeyValues
    candidate_count: int
    selection_reason: str | None
    tie_breakers: dict[str, Any]
    error_type: AllocationErrorLiteral | None
    detailed_reason: str | None
    suggested_actions: list[str]
    capacity_before: int | None
    capacity_after: int | None
    mentor_state_delta: MentorStateDelta | None
    stage_candidate_counts: dict[TraceStageName, int]
    trace_final_status: str | None
    trace_final_reason: str | None
    trace_failure_stage: TraceStageName | None
    trace_stage_flags: TraceStageFlags | None
    rule_reason_code: str | None
    rule_reason_text: str | None
    rule_reason_details: Mapping[str, Any] | None
    fairness_reason_code: str | None
    fairness_reason_text: str | None
    alerts: list[AllocationAlertRecord]
    invalid_center_alerts: list[Mapping[str, object | None]]
    join_key_mismatches: list[Mapping[str, object]]
    alias_autofill: int
    alias_unmatched: int
    phase_rule_trace: list[Mapping[str, Any]]
    pool_mismatch_detected: bool


class TraceStageRecord(TypedDict):
    """نتایج هر مرحلهٔ تریس تخصیص برای مقاصد Explainability."""

    stage: TraceStageName
    column: str
    expected_value: Any
    total_before: int
    total_after: int
    matched: bool
    expected_op: str | None
    expected_threshold: Any | None
    extras: Mapping[str, Any] | None
