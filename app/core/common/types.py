"""تعریف قراردادهای دادهٔ حوزهٔ Eligibility Matrix (Core-only, بدون I/O).

این ماژول صرفاً تایپ‌ها را نگه می‌دارد و منطق ندارد. نگاشت کلیدهای join به
کمک :class:`JoinKeyValues` در قالب ساختار فقط‌خواندنی و با اجبار «۶ مقدار عددی»
ذخیره می‌شود تا خطاهای داده‌ای به‌سرعت شناسایی شوند.

مثال:
    >>> from app.core.common.types import JoinKeyValues
    >>> keys = JoinKeyValues({
    ...   "کدرشته": 1201,
    ...   "گروه_آزمایشی": 1,
    ...   "جنسیت": 1,
    ...   "دانش_آموز_فارغ": 0,
    ...   "مرکز_گلستان_صدرا": 1,
    ...   "مالی_حکمت_بنیاد": 0,
    ... })
    >>> keys["کدرشته"]
    1201
"""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import (
    Iterable,
    Iterator,
    ItemsView,
    KeysView,
    Mapping,
    MutableMapping,
    ValuesView,
)
from types import MappingProxyType
from typing import Any, Literal, TypedDict

_NUM = re.compile(r"(\d+)")


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


class JoinKeyValues(Mapping[str, int]):
    """نگهدارندهٔ فقط‌خواندنی برای ۶ کلید join به‌صورت اعداد صحیح.

    این کلاس ترتیب درج و نام‌های قراردادی «کدرشته»، «جنسیت»،
    «دانش_آموز_فارغ»، «مرکز_گلستان_صدرا»، «مالی_حکمت_بنیاد» و «کد_مدرسه» را
    حفظ می‌کند و برای ساخت کلید ترکیبی (tuple یا dict) بدون نشتی ``Any``
    استفاده می‌شود.

    مثال کوتاه::

        >>> keys = JoinKeyValues({
        ...     "کدرشته": 1201,
        ...     "جنسیت": 1,
        ...     "دانش_آموز_فارغ": 0,
        ...     "مرکز_گلستان_صدرا": 1,
        ...     "مالی_حکمت_بنیاد": 0,
        ...     "کد_مدرسه": 10,
        ... })
        >>> keys["کدرشته"]
        1201
    """

    __slots__ = ("_items", "_mapping")

    _items: tuple[tuple[str, int], ...]
    _mapping: Mapping[str, int]

    def __init__(
        self,
        data: Mapping[str, int] | MutableMapping[str, int],
        *,
        expected_keys: Iterable[str] | None = None,
    ):
        ordered: OrderedDict[str, int] = OrderedDict()
        for key, value in data.items():
            normalized_key = str(key)
            if not isinstance(value, int):
                raise TypeError(f"Join key '{normalized_key}' must be int")
            ordered[normalized_key] = value

        if len(ordered) != 6:
            raise ValueError("JoinKeyValues must contain exactly six entries")

        if expected_keys is not None:
            expected = tuple(str(key) for key in expected_keys)
            missing = tuple(key for key in expected if key not in ordered)
            extra = tuple(key for key in ordered if key not in expected)
            if missing or extra:
                raise ValueError("JoinKeyValues keys mismatch; " f"missing={missing} extra={extra}")
            if tuple(ordered.keys()) != expected:
                raise ValueError(
                    "JoinKeyValues order mismatch; expected "
                    f"{expected} got {tuple(ordered.keys())}"
                )

        object.__setattr__(self, "_items", tuple(ordered.items()))
        object.__setattr__(self, "_mapping", MappingProxyType(dict(ordered)))

    def __setattr__(
        self, name: str, value: object
    ) -> None:  # pragma: no cover - immutability guard
        raise AttributeError("JoinKeyValues is immutable")

    def __delattr__(self, name: str) -> None:  # pragma: no cover - immutability guard
        raise AttributeError("JoinKeyValues is immutable")

    def __getitem__(self, key: str) -> int:  # pragma: no cover - Mapping API
        """دسترسی مستقیم به مقدار هر کلید join (همیشه ``int``)."""

        return self._mapping[key]

    def __iter__(self) -> Iterator[str]:  # pragma: no cover - Mapping API
        """تکرار کلیدها با حفظ ترتیب قراردادی."""

        return iter(self._mapping)

    def __len__(self) -> int:  # pragma: no cover - Mapping API
        """تعداد کلیدها که همواره ۶ است."""

        return len(self._items)

    def __contains__(self, key: object) -> bool:  # pragma: no cover - Mapping API
        """بررسی وجود کلید با احترام به نوع ``str`` و ترتیب اصلی."""

        return isinstance(key, str) and key in self._mapping

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
        missing = [key for key in expected_keys if key not in data]
        if missing:
            raise ValueError(f"join key values missing for: {', '.join(missing)}")

        ordered: OrderedDict[str, int] = OrderedDict()
        for key in expected_keys:
            raw_value = data[key]
            try:
                coerced = int(raw_value)
            except (TypeError, ValueError):
                raise TypeError(f"Join key '{key}' must be int-convertible")
            ordered[key] = coerced

        return cls(ordered, expected_keys=expected_keys)


# سازگاری نامی با نسخه‌های قبلی
JoinKeys = JoinKeyValues
JoinKeysDF = JoinKeyValues

__all__ = [
    "natural_key",
    "JoinKeyValues",
    "JoinKeys",
    "JoinKeysDF",
    "StudentRow",
    "MentorRow",
    "AllocationErrorLiteral",
    "AllocationAlertRecord",
    "MentorStateSnapshot",
    "MentorStateDelta",
    "AllocationLogRecord",
    "TraceStageLiteral",
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
    stage_candidate_counts: dict[str, int]
    rule_reason_code: str | None
    rule_reason_text: str | None
    rule_reason_details: Mapping[str, Any] | None
    fairness_reason_code: str | None
    fairness_reason_text: str | None
    alerts: list[AllocationAlertRecord]
    alias_autofill: int
    alias_unmatched: int
    phase_rule_trace: list[Mapping[str, Any]]


TraceStageLiteral = Literal[
    "type",
    "group",
    "gender",
    "graduation_status",
    "center",
    "finance",
    "school",
    "capacity_gate",
]


CANONICAL_TRACE_ORDER: tuple[TraceStageLiteral, ...] = (
    "type",
    "group",
    "gender",
    "graduation_status",
    "center",
    "finance",
    "school",
    "capacity_gate",
)


class TraceStageRecord(TypedDict):
    """نتایج هر مرحلهٔ تریس تخصیص برای مقاصد Explainability."""

    stage: TraceStageLiteral
    column: str
    expected_value: Any
    total_before: int
    total_after: int
    matched: bool
    expected_op: str | None
    expected_threshold: Any | None
    extras: Mapping[str, Any] | None
