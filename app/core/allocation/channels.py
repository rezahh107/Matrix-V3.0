from __future__ import annotations

from collections.abc import Iterable
from typing import SupportsInt, cast

import pandas as pd

from app.core.common.columns import ensure_series
from app.core.common.domain import (
    BuildConfig,
    Status,
    StudentBindingKind,
    classify_student_binding,
)
from app.core.common.enum_compat import StrEnum
from app.core.common.isin_guard import isin_mask, require_isin_values
from app.core.policy.config import AllocationChannelConfig
from app.core.policy_loader import PolicyConfig


class AllocationChannel(StrEnum):
    """کانال‌های استاندارد تخصیص دانش‌آموز."""

    SCHOOL = "SCHOOL"
    GOLESTAN = "GOLESTAN"
    SADRA = "SADRA"
    GENERIC = "GENERIC"


def _to_int_safe(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str, bytes, bytearray)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    if hasattr(value, "__int__"):
        try:
            return int(cast(SupportsInt, value))
        except (TypeError, ValueError):
            return None
    return None


def _column_as_int(df: pd.DataFrame, column: str | None) -> pd.Series | None:
    if column is None or column not in df.columns:
        return None
    values = ensure_series(df[column])
    numeric = pd.to_numeric(values, errors="coerce")
    return numeric.astype("Int64")


def _ensure_int_values(name: str, values: object) -> tuple[int, ...]:
    if values is None:
        return tuple()
    checked = require_isin_values(name, values)
    normalized: list[int] = []
    for item in cast(Iterable[object], checked):
        if not isinstance(item, int):
            raise TypeError(f"{name} must contain only ints; got {item!r}")
        normalized.append(int(item))
    return tuple(normalized)


def _graduation_status_series(students_df: pd.DataFrame, policy: PolicyConfig) -> pd.Series | None:
    try:
        status_column = policy.stage_column("graduation_status")
    except KeyError:
        return None
    return _column_as_int(students_df, status_column)


def _active_student_mask(students_df: pd.DataFrame, policy: PolicyConfig) -> pd.Series:
    rules = policy.allocation_channels
    active_status_values = _ensure_int_values(
        "allocation_channels.active_status_values", rules.active_status_values
    )
    if not active_status_values:
        return pd.Series(True, index=students_df.index, dtype=bool)
    column = rules.educational_status_column
    if not column or column not in students_df.columns:
        return pd.Series(True, index=students_df.index, dtype=bool)
    status_series = _column_as_int(students_df, column)
    if status_series is None:
        return pd.Series(True, index=students_df.index, dtype=bool)
    mask = cast(
        pd.Series,
        isin_mask(
            status_series,
            active_status_values,
            name="allocation_channels.active_status_values",
        ),
    ) | status_series.isna()
    return mask.fillna(True)


def _apply_center_channel(
    result: pd.Series,
    center_values: pd.Series | None,
    *,
    rules: AllocationChannelConfig,
    channel: AllocationChannel,
) -> None:
    if center_values is None:
        return
    center_ids = _ensure_int_values(
        f"allocation_channels.center_channels.{channel.value}",
        rules.center_channels.get(channel.value, tuple()),
    )
    if not center_ids:
        return
    mask = cast(
        pd.Series,
        isin_mask(
            center_values,
            center_ids,
            name=f"allocation_channels.center_channels.{channel.value}",
        ),
    )
    if mask.empty:
        return
    unresolved = result == AllocationChannel.GENERIC
    result.loc[mask & unresolved] = channel


def _channel_for_center(center_value: object, policy: PolicyConfig) -> AllocationChannel | None:
    center_id = _to_int_safe(center_value)
    if center_id is None:
        return None
    rules = policy.allocation_channels
    for channel in (AllocationChannel.GOLESTAN, AllocationChannel.SADRA):
        ids: Iterable[int] = rules.center_channels.get(channel.value, tuple())
        if center_id in ids:
            return channel
    return None


def _is_active_student(student: pd.Series, policy: PolicyConfig) -> bool:
    rules = policy.allocation_channels
    if not rules.active_status_values:
        return True
    column = rules.educational_status_column
    if not column or column not in student:
        return True
    status_value = _to_int_safe(student.get(column))
    return status_value is None or status_value in rules.active_status_values


def _student_binding(student: pd.Series, policy: PolicyConfig) -> StudentBindingKind:
    try:
        cfg = BuildConfig(policy=policy)
    except ValueError:
        cfg = None
    if cfg is not None:
        return classify_student_binding(student, cfg=cfg)

    school_code = _to_int_safe(student.get(policy.columns.school_code))
    try:
        status_column = policy.stage_column("graduation_status")
    except KeyError:
        status_column = None
    status_value = _to_int_safe(student.get(status_column)) if status_column else None
    is_student = status_value == Status.STUDENT if status_value is not None else True
    if (
        school_code is not None
        and school_code in policy.allocation_channels.school_codes
        and is_student
    ):
        return StudentBindingKind.SCHOOL
    return StudentBindingKind.NORMAL


def derive_allocation_channel(student: pd.Series, policy: PolicyConfig) -> AllocationChannel:
    """کانال تخصیص دانش‌آموز را طبق Policy برمی‌گرداند.

    ابتدا دانش‌آموزان با کد مدرسهٔ موجود در ``allocation_channels.school_codes`` و
    وضعیت تحصیلی فعال در کانال SCHOOL قرار می‌گیرند؛ سپس ستون مرحلهٔ مرکز و ستون
    ثبت‌نام (در صورت تعریف) برای تشخیص GOLESTAN/SADRA بررسی می‌شوند و در صورت عدم
    تطابق، مقدار GENERIC بازگردانده می‌شود.

    مثال:
        >>> import pandas as pd  # doctest: +SKIP
        >>> policy = ...  # پیکربندی PolicyConfig با قوانین کانال  # doctest: +SKIP
        >>> row = pd.Series({"کد مدرسه": 10, "student_educational_status": 0})  # doctest: +SKIP
        >>> derive_allocation_channel(row, policy)  # doctest: +SKIP
        <AllocationChannel.SCHOOL: 'SCHOOL'>
    """

    rules = policy.allocation_channels
    binding = _student_binding(student, policy)
    if binding is StudentBindingKind.SCHOOL and _is_active_student(student, policy):
        return AllocationChannel.SCHOOL

    try:
        center_column = policy.stage_column("center")
    except KeyError:
        center_column = None
    if center_column and center_column in student:
        center_channel = _channel_for_center(student.get(center_column), policy)
        if center_channel:
            return center_channel

    registration_column = rules.registration_center_column
    if registration_column and registration_column in student:
        registration_channel = _channel_for_center(student.get(registration_column), policy)
        if registration_channel:
            return registration_channel

    return AllocationChannel.GENERIC


def derive_channels_for_students(students_df: pd.DataFrame, policy: PolicyConfig) -> pd.Series:
    """برچسب‌گذاری کانال تخصیص به‌صورت برداری و دترمینیسیک."""

    if students_df.empty:
        return pd.Series(dtype=object, index=students_df.index)

    result = pd.Series(
        [AllocationChannel.GENERIC] * len(students_df), index=students_df.index, dtype=object
    )
    rules = policy.allocation_channels

    if not students_df.empty:
        bindings = students_df.apply(lambda row: _student_binding(row, policy), axis=1)
        if rules.school_codes:
            active_mask = _active_student_mask(students_df, policy)
            school_mask = bindings.eq(StudentBindingKind.SCHOOL) & active_mask
            result.loc[school_mask] = AllocationChannel.SCHOOL

    try:
        center_column = policy.stage_column("center")
    except KeyError:
        center_column = None

    for column in (center_column, rules.registration_center_column):
        series = _column_as_int(students_df, column)
        _apply_center_channel(result, series, rules=rules, channel=AllocationChannel.GOLESTAN)
        _apply_center_channel(result, series, rules=rules, channel=AllocationChannel.SADRA)

    return result


__all__ = [
    "AllocationChannel",
    "derive_allocation_channel",
    "derive_channels_for_students",
]
