"""ابزارهای کاننیکال‌سازی دیتافریم‌ها در لایهٔ Infra با Crosswalk Policy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

import pandas as pd

from app.core.build_matrix import prepare_crosswalk_mappings
from app.core.canonical_frames import canonicalize_students_frame
from app.core.common.columns import canonicalize_headers
from app.core.common.normalization import normalize_fa
from app.core.policy_loader import (
    MentorPoolGovernanceConfig,
    MentorStatus,
    PolicyConfig,
)

__all__ = [
    "build_student_group_crosswalk",
    "canonicalize_students_frame_with_crosswalk",
    "canonicalize_mentor_pool_frame",
]

_RAW_GROUP_COLUMNS: Final[tuple[str, ...]] = ("کدرشته خام", "کد گروه خام", "کدرشته")
_TARGET_GROUP_COLUMN: Final[str] = "کد گروه"
_NAME_COLUMN: Final[str] = "گروه آزمایشی"


def build_student_group_crosswalk(crosswalk_groups_df: pd.DataFrame) -> dict[str | int, int]:
    """ساخت نگاشت Crosswalk کدرشته دانش‌آموز از شیت مرجع گروه‌ها.

    این تابع همان دیتافریم Crosswalk را که برای ساخت استخر منتورها استفاده
    می‌شود مصرف می‌کند تا دانش‌آموز و استخر روی bucketهای مشترک قرار گیرند.
    """

    normalized = canonicalize_headers(crosswalk_groups_df.copy(), header_mode="fa")
    required = {_TARGET_GROUP_COLUMN, _NAME_COLUMN}
    missing = required.difference(normalized.columns)
    if missing:
        raise ValueError(f"Crosswalk groups frame missing columns: {sorted(missing)}")

    name_to_code, _, _, _ = prepare_crosswalk_mappings(normalized)
    crosswalk: dict[str | int, int] = {
        normalize_fa(name): int(code) for name, code in name_to_code.items()
    }

    target_series = pd.to_numeric(normalized[_TARGET_GROUP_COLUMN], errors="coerce")
    for raw_name, target_value in zip(normalized[_NAME_COLUMN], target_series):
        if pd.isna(target_value):
            continue
        normalized_name = normalize_fa(raw_name)
        if normalized_name:
            crosswalk[normalized_name] = int(target_value)
    for raw_column in _RAW_GROUP_COLUMNS:
        if raw_column not in normalized.columns:
            continue
        raw_series = pd.to_numeric(normalized[raw_column], errors="coerce")
        for raw_value, target_value in zip(raw_series, target_series):
            if pd.isna(raw_value) or pd.isna(target_value):
                continue
            crosswalk[int(raw_value)] = int(target_value)

    return crosswalk


def canonicalize_students_frame_with_crosswalk(
    students_df: pd.DataFrame,
    *,
    policy: PolicyConfig,
    group_crosswalk: Mapping[str | int, int],
) -> pd.DataFrame:
    """کاننیکال‌سازی دیتافریم دانش‌آموز با اعمال Crosswalk کدرشته."""

    return canonicalize_students_frame(
        students_df, policy=policy, group_code_crosswalk=group_crosswalk
    )


def canonicalize_mentor_pool_frame(
    mentors_df: pd.DataFrame,
    *,
    governance: MentorPoolGovernanceConfig,
) -> pd.DataFrame:
    """کاننیکال‌سازی دیتافریم منتورها با اعتبارسنجی وضعیت."""

    canonical = canonicalize_headers(mentors_df.copy(), header_mode="en")
    allowed_statuses = set(governance.allowed_statuses)
    if "mentor_status" in canonical.columns:
        normalized_status = pd.Series(index=canonical.index, dtype=object)
        for idx, value in canonical["mentor_status"].items():
            try:
                status = MentorStatus.from_value(value)
            except ValueError as exc:
                raise ValueError(
                    f"Unknown mentor_status value '{value}' in mentor pool frame"
                ) from exc
            if status not in allowed_statuses:
                raise ValueError(
                    "mentor_status value is not allowed by governance.allowed_statuses"
                )
            normalized_status.iloc[idx] = status.value
        canonical["mentor_status"] = normalized_status
    return canonical
