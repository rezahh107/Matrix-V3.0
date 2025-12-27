"""فیلترهای خالص برای کلیدهای اتصال دانش‌آموز به پشتیبان (Core-only).

این ماژول هیچ I/O انجام نمی‌دهد و تنها عملیات برداری روی DataFrameهای
pandas را اجرا می‌کند. هر تابع یکی از مراحل «Allocation 7-Pack» را پوشش
می‌دهد و در نهایت `apply_join_filters` ترتیب استاندارد را اعمال می‌کند.
نام ستون‌ها به‌طور کامل از Policy خوانده می‌شود تا تغییرات بدون دستکاری
کد اعمال شوند.

مثال ساده::

    >>> import pandas as pd
    >>> from app.core.common.filters import apply_join_filters
    >>> pool = pd.DataFrame({
    ...     "کدرشته": [1, 3],
    ...     "گروه آزمایشی": ["تجربی", "ریاضی"],
    ...     "جنسیت": [1, 1],
    ...     "دانش آموز فارغ": [0, 0],
    ...     "مرکز گلستان صدرا": [1, 1],
    ...     "مالی حکمت بنیاد": [0, 0],
    ...     "کد مدرسه": [3581, 4001],
    ... })
    >>> student = {
    ...     "کدرشته": 1,
    ...     "گروه_آزمایشی": "تجربی",
    ...     "جنسیت": 1,
    ...     "دانش_آموز_فارغ": 0,
    ...     "مرکز_گلستان_صدرا": 1,
    ...     "مالی_حکمت_بنیاد": 0,
    ...     "کد_مدرسه": 3581,
    ... }
    >>> apply_join_filters(pool, student).shape[0]
    1
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol

import pandas as pd

from app.core.common.columns import ensure_series
from app.core.common.join_keys import (
    JoinKeyCanonicalizationError,
    StudentSchoolCode,
    canonicalize_join_key_value,
    finance_mask_series,
    sanitize_school_series,
    school_mask_series,
)
from app.core.common.join_resolver import JoinKeyResolver

from ..policy_loader import PolicyConfig, load_policy


def filter_school_by_value(
    frame: pd.DataFrame, column: str, target: int
) -> tuple[pd.DataFrame, bool]:
    """فیلتر کردن ستون مدرسه با رعایت نرمال‌سازی و گزارش تطبیق."""

    column_series = frame[column]
    if pd.api.types.is_integer_dtype(column_series):
        mask = column_series == target
    else:
        sanitized = sanitize_school_series(column_series)
        mask = sanitized == target
    matched = bool(mask.any())
    if not matched:
        return frame, False
    return frame.loc[mask], True


def resolve_student_school_code(
    student: Mapping[str, object],
    policy: PolicyConfig,
) -> StudentSchoolCode:
    """استخراج مقدار استاندارد کد مدرسه با درنظرگرفتن سیاست wildcard."""
    resolver = JoinKeyResolver(policy)
    return resolver.resolve_school(student)


class FilterFunc(Protocol):
    def __call__(
        self,
        pool: pd.DataFrame,
        student: Mapping[str, object],
        policy: PolicyConfig,
        *,
        student_join_map: Mapping[str, int] | None = None,
    ) -> pd.DataFrame: ...


FilterTracker = Callable[[str, int], None]

__all__ = [
    "StudentSchoolCode",
    "FilterTracker",
    "filter_by_type",
    "filter_by_group",
    "filter_by_gender",
    "filter_by_graduation_status",
    "filter_by_center",
    "filter_by_finance",
    "filter_by_school",
    "filter_school_by_value",
    "resolve_student_school_code",
    "apply_join_filters",
]


def _student_value(student: Mapping[str, object], column: str) -> object:
    """بازیابی مقدار ستون از دانش‌آموز با پشتیبانی از آندرلاین/فاصله."""

    if column in student:
        return student[column]
    normalized = column.replace(" ", "_")
    if normalized in student:
        return student[normalized]
    raise KeyError(f"Student row missing value for '{column}'")


def _eq_filter(frame: pd.DataFrame, column: str, value: object) -> pd.DataFrame:
    """اعمال فیلتر مساوی روی دیتافریم بدون تغییر ورودی اصلی."""

    return frame.loc[frame[column] == value]


def _filter_by_stage(
    pool: pd.DataFrame,
    student: Mapping[str, object],
    policy: PolicyConfig,
    stage: str,
    *,
    student_join_map: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    column = policy.stage_column(stage)
    normalized = column.replace(" ", "_")
    value: object
    if student_join_map and normalized in student_join_map:
        value = student_join_map[normalized]
    else:
        value = _student_value(student, column)
    if stage == "gender":
        try:
            gender_value = canonicalize_join_key_value(column, value, policy=policy)
        except JoinKeyCanonicalizationError:
            return pool.iloc[0:0]
        return _eq_filter(pool, column, gender_value)
    return _eq_filter(pool, column, value)


def filter_by_type(
    pool: pd.DataFrame,
    student: Mapping[str, object],
    policy: PolicyConfig | None = None,
    *,
    student_join_map: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    """فیلتر مرحلهٔ type بر اساس ستون اعلام‌شده در Policy."""

    if policy is None:
        policy = load_policy()
    return _filter_by_stage(
        pool,
        student,
        policy,
        "type",
        student_join_map=student_join_map,
    )


def filter_by_group(
    pool: pd.DataFrame,
    student: Mapping[str, object],
    policy: PolicyConfig | None = None,
    *,
    student_join_map: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    """فیلتر مرحلهٔ group با ستون پویا از Policy."""

    if policy is None:
        policy = load_policy()
    return _filter_by_stage(
        pool,
        student,
        policy,
        "group",
        student_join_map=student_join_map,
    )


def filter_by_gender(
    pool: pd.DataFrame,
    student: Mapping[str, object],
    policy: PolicyConfig | None = None,
    *,
    student_join_map: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    """فیلتر gender با ستون تعریف‌شده در Policy."""

    if policy is None:
        policy = load_policy()
    return _filter_by_stage(
        pool,
        student,
        policy,
        "gender",
        student_join_map=student_join_map,
    )


def filter_by_graduation_status(
    pool: pd.DataFrame,
    student: Mapping[str, object],
    policy: PolicyConfig | None = None,
    *,
    student_join_map: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    """فیلتر graduation_status با ستون پویا."""

    if policy is None:
        policy = load_policy()
    return _filter_by_stage(
        pool,
        student,
        policy,
        "graduation_status",
        student_join_map=student_join_map,
    )


def filter_by_center(
    pool: pd.DataFrame,
    student: Mapping[str, object],
    policy: PolicyConfig | None = None,
    *,
    student_join_map: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    """فیلتر center با ستون پویا."""

    if policy is None:
        policy = load_policy()
    column = policy.stage_column("center")
    resolver = JoinKeyResolver(policy)
    effective = resolver.resolve_center(student, student_join_map=student_join_map)
    if effective.center_code is None:
        return pool
    center_value = int(effective.center_code)
    series = pd.to_numeric(ensure_series(pool[column]), errors="coerce").astype("Int64")
    mask = series.eq(0) if center_value == 0 else series.eq(0) | series.eq(center_value)
    return pool.loc[mask.fillna(False)]


def filter_by_finance(
    pool: pd.DataFrame,
    student: Mapping[str, object],
    policy: PolicyConfig | None = None,
    *,
    student_join_map: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    """فیلتر finance با ستون پویا."""

    if policy is None:
        policy = load_policy()
    column = policy.stage_column("finance")
    resolver = JoinKeyResolver(policy)
    effective = resolver.resolve_finance(student, student_join_map=student_join_map)
    if effective.finance_code is None:
        return pool.iloc[0:0]
    mask = finance_mask_series(
        ensure_series(pool[column]),
        student_variants=effective.finance_variants,
        policy=policy,
    )
    return pool.loc[mask]


def filter_by_school(
    pool: pd.DataFrame,
    student: Mapping[str, object],
    policy: PolicyConfig | None = None,
    *,
    student_join_map: Mapping[str, int] | None = None,
) -> pd.DataFrame:
    """فیلتر school با ستون پویا."""

    if policy is None:
        policy = load_policy()
    column = policy.stage_column("school")
    resolver = JoinKeyResolver(policy)
    school_code = resolver.resolve_school(student, student_join_map=student_join_map)
    if school_code.value is None:
        # If school code could not be resolved, no school-specific filtering can be applied.
        # This occurs when the value is missing and there's no wildcard policy.
        return pool
    target = int(school_code.value)
    constraint_mask: pd.Series | None = None
    constraint_col = "has_school_constraint"
    if constraint_col in pool.columns:
        series = pool[constraint_col]
        constraint_mask = pd.Series(series.fillna(False).astype(bool), index=pool.index)
    elif "mentor_school_binding_mode" in pool.columns:
        restricted_mode = policy.mentor_school_binding.restricted_mode
        binding_series = pool["mentor_school_binding_mode"].astype("string").fillna("")
        constraint_mask = binding_series.str.strip().eq(restricted_mode)

    mask = school_mask_series(
        ensure_series(pool[column]),
        student_school=target,
        empty_as_zero=policy.school_code_empty_as_zero,
        constraint_series=constraint_mask,
    )
    return pool.loc[mask]


def apply_join_filters(
    pool: pd.DataFrame,
    student: Mapping[str, object],
    *,
    policy: PolicyConfig | None = None,
    student_join_map: Mapping[str, int] | None = None,
    tracker: FilterTracker | None = None,
) -> pd.DataFrame:
    """اجرای ترتیبی هفت فیلتر join روی استخر کاندید بدون mutate کردن ورودی."""

    if policy is None:
        policy = load_policy()

    current = pool
    for index, (stage_name, fn) in enumerate(zip(_FILTER_STAGE_NAMES, _FILTER_SEQUENCE)):
        current = fn(
            current,
            student,
            policy,
            student_join_map=student_join_map,
        )
        if tracker is not None:
            tracker(stage_name, int(current.shape[0]))
        if current.empty and tracker is not None:
            for remaining in _FILTER_STAGE_NAMES[index + 1 :]:
                tracker(remaining, 0)
            break
        if current.empty:
            break
    return current


_FILTER_SEQUENCE: Sequence[FilterFunc] = (
    filter_by_type,
    filter_by_group,
    filter_by_gender,
    filter_by_graduation_status,
    filter_by_center,
    filter_by_finance,
    filter_by_school,
)

_FILTER_STAGE_NAMES: Sequence[str] = (
    "type",
    "group",
    "gender",
    "graduation_status",
    "center",
    "finance",
    "school",
)
