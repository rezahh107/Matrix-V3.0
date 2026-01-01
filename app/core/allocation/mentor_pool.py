"""توابع حاکمیت استخر منتورها (POOL_01) با ورودی Override ساده.

این ماژول هیچ I/O یا وابستگی به Qt ندارد و صرفاً روی DataFrame
کار می‌کند تا بر اساس پیکربندی Policy یا overrideهای UI/CLI منتورها
را فعال/غیرفعال کند.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from app.core.common.columns import canonicalize_headers
from app.core.common.isin_guard import isin_mask
from app.core.common.types import CANONICAL_JOIN_KEYS
from app.core.policy_loader import MentorPoolGovernanceConfig, MentorStatus

__all__ = [
    "compute_effective_status",
    "filter_active_mentors",
    "apply_mentor_pool_governance",
    "apply_manager_mentor_governance",
]


@dataclass(frozen=True)
class PoolGovernanceTraceEntry:
    stage_name: str
    raw_rows: int
    after_rows: int
    removed_rows: int
    removed_breakdown: dict[str, int]
    distribution_before: dict[str, dict[int, int]]
    distribution_after: dict[str, dict[int, int]]
    profile_rows_before: int
    profile_rows_after: int
    unique_mentor_ids_before: int | None
    unique_mentor_ids_after: int | None

    def to_record(self) -> dict[str, object]:
        return {
            "stage_name": self.stage_name,
            "raw_rows": self.raw_rows,
            "after_rows": self.after_rows,
            "removed_rows": self.removed_rows,
            "removed_breakdown": dict(self.removed_breakdown),
            "distribution_before": self.distribution_before,
            "distribution_after": self.distribution_after,
            "profile_rows_before": self.profile_rows_before,
            "profile_rows_after": self.profile_rows_after,
            "unique_mentor_ids_before": self.unique_mentor_ids_before,
            "unique_mentor_ids_after": self.unique_mentor_ids_after,
        }


def _distribution_counts(frame: pd.DataFrame) -> dict[str, dict[int, int]]:
    distributions: dict[str, dict[int, int]] = {}
    for column in ("group_code", "gender", "graduation_status"):
        if column not in frame.columns:
            continue
        series = pd.to_numeric(frame[column], errors="coerce").dropna().astype(int)
        counts = series.value_counts().sort_index()
        distributions[column] = {int(key): int(value) for key, value in counts.items()}
    return distributions


def _unique_mentor_ids(frame: pd.DataFrame) -> int | None:
    if "mentor_id" not in frame.columns:
        return None
    series = pd.to_numeric(frame["mentor_id"], errors="coerce").dropna().astype(int)
    return int(series.nunique())


def _normalize_overrides(
    overrides: Mapping[int | str | float, bool] | None,
) -> dict[int | str | float, bool]:
    normalized: dict[int | str | float, bool] = {}
    if not overrides:
        return normalized
    for raw_id, enabled in overrides.items():
        try:
            mentor_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        normalized[mentor_id] = bool(enabled)
    return normalized


def compute_effective_status(
    mentors_df: pd.DataFrame,
    governance: MentorPoolGovernanceConfig,
    overrides: Mapping[int | str | float, bool] | None = None,
) -> pd.Series:
    """محاسبهٔ وضعیت مؤثر هر پشتیبان بر اساس Policy و overrideهای نوبت جاری.

    پارامترها
    ----------
    mentors_df:
        دیتافریم اولیهٔ پشتیبان‌ها که باید ستون ``mentor_id`` داشته باشد.
    governance:
        تنظیمات حاکمیت استخر از Policy.
    overrides:
        نگاشت اختیاری ``mentor_id`` → ``enabled`` برای فعال/غیرفعال‌سازی نوبتی.

    مثال
    -----
    >>> import pandas as pd
    >>> from app.core.policy_loader import MentorPoolGovernanceConfig, MentorStatus
    >>> df = pd.DataFrame({"mentor_id": [1, 2]})
    >>> config = MentorPoolGovernanceConfig(
    ...     default_status=MentorStatus.ACTIVE,
    ...     mentor_status_map={2: MentorStatus.INACTIVE},
    ...     allowed_statuses=(MentorStatus.ACTIVE, MentorStatus.INACTIVE),
    ... )
    >>> compute_effective_status(df, config).tolist()
    [<MentorStatus.ACTIVE: 'active'>, <MentorStatus.INACTIVE: 'inactive'>]
    >>> compute_effective_status(df, config, overrides={2: True}).tolist()
    [<MentorStatus.ACTIVE: 'active'>, <MentorStatus.ACTIVE: 'active'>]
    """

    if "mentor_id" not in mentors_df.columns:
        raise KeyError("mentors_df must contain 'mentor_id' column")

    allowed_statuses = set(governance.allowed_statuses)
    if not allowed_statuses:
        raise ValueError("MentorPoolGovernanceConfig.allowed_statuses must not be empty")
    if governance.default_status not in allowed_statuses:
        raise ValueError("default_status must be part of allowed_statuses")

    for status in governance.mentor_status_map.values():
        if status not in allowed_statuses:
            raise ValueError("mentor_status_map contains status outside allowed_statuses")

    canonical = canonicalize_headers(mentors_df, header_mode="en")

    def _as_series(values: pd.Series | pd.DataFrame, column: str) -> pd.Series:
        if isinstance(values, pd.DataFrame):
            return values.iloc[:, 0]
        return values.rename(column)

    mentor_id_values = canonical["mentor_id"]
    mentor_ids = pd.to_numeric(_as_series(mentor_id_values, "mentor_id"), errors="coerce")
    base_statuses = pd.Series(governance.default_status, index=canonical.index, dtype=object)

    def _parse_status(value: object) -> MentorStatus | None:
        if pd.isna(value):
            return None
        try:
            status = MentorStatus.from_value(value)
        except ValueError:
            raise ValueError(f"Unknown mentor_status value '{value}'")
        if status not in allowed_statuses:
            raise ValueError("mentor_status value is not allowed by governance.allowed_statuses")
        return status

    if "mentor_status" in canonical.columns:
        parsed_statuses = _as_series(canonical["mentor_status"], "mentor_status").map(_parse_status)
        base_statuses = base_statuses.where(parsed_statuses.isna(), parsed_statuses)

    policy_status = mentor_ids.map(governance.mentor_status_map)
    policy_status = policy_status.where(
        isin_mask(policy_status, allowed_statuses, name="allowed_statuses"),
        pd.NA,
    )
    statuses = base_statuses.where(policy_status.isna(), policy_status)

    override_map: dict[int, MentorStatus] = {}
    disabled_status = governance.disabled_status
    if overrides:
        for raw_id, enabled in overrides.items():
            try:
                mentor_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            override_map[mentor_id] = MentorStatus.ACTIVE if bool(enabled) else disabled_status

    if override_map:
        override_status = mentor_ids.map(override_map)
        statuses = statuses.where(override_status.isna(), override_status)

    invalid_statuses = statuses[
        ~isin_mask(statuses, governance.allowed_statuses, name="allowed_statuses")
    ]
    if not invalid_statuses.empty:
        raise ValueError(
            "mentor_status contains values outside governance.allowed_statuses: "
            f"{invalid_statuses.tolist()}"
        )

    return statuses


def filter_active_mentors(
    mentors_df: pd.DataFrame,
    governance: MentorPoolGovernanceConfig,
    overrides: Mapping[int | str | float, bool] | None = None,
    *,
    attach_status: bool = False,
    status_column: str = "mentor_status",
) -> pd.DataFrame:
    """اعمال حاکمیت استخر و بازگرداندن استخر فعال.

    این تابع تغییری در ورودی ایجاد نمی‌کند و دیتافریم جدیدی می‌سازد که
    تنها پشتیبان‌های با وضعیت ``active`` را نگه می‌دارد. در صورت نیاز می‌توان
    وضعیت مؤثر را به‌صورت ستونی جداگانه نیز ضمیمه کرد.

    مثال
    -----
    >>> import pandas as pd
    >>> from app.core.policy_loader import MentorPoolGovernanceConfig, MentorStatus
    >>> df = pd.DataFrame({"mentor_id": [10, 20], "نام": ["الف", "ب"]})
    >>> config = MentorPoolGovernanceConfig(
    ...     default_status=MentorStatus.ACTIVE,
    ...     mentor_status_map={20: MentorStatus.INACTIVE},
    ...     allowed_statuses=(MentorStatus.ACTIVE, MentorStatus.INACTIVE),
    ... )
    >>> filter_active_mentors(df, config)
       mentor_id نام
    0        10  الف
    >>> filter_active_mentors(df, config, overrides={20: True}, attach_status=True)
       mentor_id نام mentor_status
    0        10  الف         active
    1        20   ب         active
    """

    canonical = canonicalize_headers(mentors_df, header_mode="en")
    statuses = compute_effective_status(canonical, governance, overrides)
    active_mask = statuses == MentorStatus.ACTIVE

    capacity_mask = pd.Series(True, index=canonical.index)
    if "remaining_capacity" in canonical.columns:
        capacity_numeric = pd.to_numeric(canonical["remaining_capacity"], errors="coerce")
        capacity_mask = capacity_numeric > 0

    filtered_mask = active_mask & capacity_mask
    filtered = mentors_df.loc[filtered_mask].copy()

    if attach_status:
        filtered.loc[:, status_column] = statuses.loc[filtered.index].map(lambda s: s.value)

    return filtered


def apply_mentor_pool_governance(
    mentors_df: pd.DataFrame | None,
    governance: MentorPoolGovernanceConfig,
    *,
    overrides: Mapping[int | str | float, bool] | None = None,
    enable_trace: bool = False,
) -> pd.DataFrame:
    """اعمال حاکمیت استخر منتورها بر اساس Policy و override نوبتی.

    پارامترها
    ----------
    mentors_df:
        دیتافریم ورودی استخر منتورها. در صورت تهی یا نبود ستون ``mentor_id``
        بدون خطا بازگردانده می‌شود.
    governance:
        پیکربندی حاکمیت استخر از Policy (MentorPoolGovernanceConfig).
    overrides:
        نگاشت اختیاری ``mentor_id`` → ``enabled`` برای فعال/غیرفعال‌سازی
        در اجرای جاری.

    خروجی
    ------
    دیتافریم فیلترشده با حفظ شِما که ویژگی ``attrs['mentor_pool_governance']``
    را شامل شمار کل، حذف‌شده و تعداد overrideها دارد. خروجی برای ورودی برابر
    دترمینیستیک است و هیچ I/O یا وابستگی Qt در Core وارد نمی‌شود.
    """

    normalized_overrides = _normalize_overrides(overrides)
    trace_entries: list[PoolGovernanceTraceEntry] = []

    if mentors_df is None:
        result = pd.DataFrame()
        result.attrs["mentor_pool_governance"] = {
            "total": 0,
            "removed": 0,
            "removed_duplicates": 0,
            "overrides_count": len(normalized_overrides),
        }
        if enable_trace:
            result.attrs["mentor_pool_governance_trace"] = []
        return result

    result = mentors_df.copy(deep=True)
    total_rows = len(result)
    if result.empty or "mentor_id" not in result.columns:
        result.attrs["mentor_pool_governance"] = {
            "total": total_rows,
            "removed": 0,
            "removed_duplicates": 0,
            "overrides_count": len(normalized_overrides),
        }
        if enable_trace:
            result.attrs["mentor_pool_governance_trace"] = []
        return result

    canonical = canonicalize_headers(result, header_mode="en")

    def _append_trace(
        stage_name: str,
        before_df: pd.DataFrame,
        after_df: pd.DataFrame,
        breakdown: dict[str, int],
    ) -> None:
        if not enable_trace:
            return
        entry = PoolGovernanceTraceEntry(
            stage_name=stage_name,
            raw_rows=int(before_df.shape[0]),
            after_rows=int(after_df.shape[0]),
            removed_rows=int(before_df.shape[0] - after_df.shape[0]),
            removed_breakdown=breakdown,
            distribution_before=_distribution_counts(before_df),
            distribution_after=_distribution_counts(after_df),
            profile_rows_before=int(before_df.shape[0]),
            profile_rows_after=int(after_df.shape[0]),
            unique_mentor_ids_before=_unique_mentor_ids(before_df),
            unique_mentor_ids_after=_unique_mentor_ids(after_df),
        )
        trace_entries.append(entry)

    subset_columns = ["mentor_id"] + [
        key for key in CANONICAL_JOIN_KEYS if key in canonical.columns
    ]
    duplicate_mask = canonical.duplicated(subset=subset_columns, keep=False)
    duplicates_removed = 0
    if duplicate_mask.any():
        keep_mask = ~canonical.duplicated(subset=subset_columns, keep="first")
        duplicates_removed = int(total_rows - keep_mask.sum())
        before = canonical.copy()
        result = result.loc[keep_mask].copy()
        canonical = canonical.loc[keep_mask].copy()
        _append_trace(
            "deduplicate_profiles",
            before,
            canonical,
            {
                "inactive_removed": 0,
                "zero_capacity_removed": 0,
                "duplicate_removed": duplicates_removed,
                "overrides_removed": 0,
                "prefilter_removed": 0,
            },
        )
    elif enable_trace:
        _append_trace(
            "deduplicate_profiles",
            canonical,
            canonical,
            {
                "inactive_removed": 0,
                "zero_capacity_removed": 0,
                "duplicate_removed": 0,
                "overrides_removed": 0,
                "prefilter_removed": 0,
            },
        )

    base_statuses = compute_effective_status(result, governance, None)
    statuses = compute_effective_status(result, governance, normalized_overrides)
    active_mask = statuses == MentorStatus.ACTIVE
    overrides_removed = int(((base_statuses == MentorStatus.ACTIVE) & ~active_mask).sum())
    inactive_removed = int((~active_mask).sum()) - overrides_removed
    if inactive_removed < 0:
        inactive_removed = 0

    status_canonical = canonical.loc[active_mask].copy()
    capacity_mask = pd.Series(True, index=status_canonical.index)
    if "remaining_capacity" in status_canonical.columns:
        capacity_numeric = pd.to_numeric(
            status_canonical["remaining_capacity"], errors="coerce"
        )
        capacity_mask = capacity_numeric > 0

    filtered_mask = active_mask.copy()
    filtered_mask.loc[status_canonical.index] = capacity_mask
    filtered = result.loc[filtered_mask].copy()
    if enable_trace:
        _append_trace(
            "status_filter",
            canonical,
            status_canonical,
            {
                "inactive_removed": inactive_removed,
                "zero_capacity_removed": 0,
                "duplicate_removed": 0,
                "overrides_removed": overrides_removed,
                "prefilter_removed": 0,
            },
        )
        _append_trace(
            "capacity_filter",
            status_canonical,
            status_canonical.loc[capacity_mask].copy(),
            {
                "inactive_removed": 0,
                "zero_capacity_removed": int((~capacity_mask).sum()),
                "duplicate_removed": 0,
                "overrides_removed": 0,
                "prefilter_removed": 0,
            },
        )
    filtered.attrs["mentor_pool_governance"] = {
        "total": total_rows,
        "removed": duplicates_removed + int((~filtered_mask).sum()),
        "removed_duplicates": duplicates_removed,
        "overrides_count": len(normalized_overrides),
    }
    if enable_trace:
        filtered.attrs["mentor_pool_governance_trace"] = [
            entry.to_record() for entry in trace_entries
        ]
    return filtered


def _normalize_manager_overrides(
    overrides: Mapping[int | str | float, bool] | None,
) -> dict[str, bool]:
    normalized: dict[str, bool] = {}
    if not overrides:
        return normalized
    for raw_id, enabled in overrides.items():
        key = str(raw_id).strip()
        if not key:
            continue
        normalized[key] = bool(enabled)
    return normalized


def apply_manager_mentor_governance(
    mentors_df: pd.DataFrame | None,
    governance: MentorPoolGovernanceConfig,
    *,
    mentor_overrides: Mapping[int | str | float, bool] | None = None,
    manager_overrides: Mapping[int | str | float, bool] | None = None,
    enable_trace: bool = False,
) -> pd.DataFrame:
    """اعمال حاکمیت مدیر→منتور به‌صورت دترمینیستیک و بدون I/O.

    ابتدا مدیران غیرفعال حذف می‌شوند و سپس وضعیت مؤثر منتورها بر اساس Policy
    و overrideهای mentor اعمال می‌گردد. خروجی شِما را حفظ می‌کند و متادیتای
    `mentor_pool_governance` را با شمارش‌های حذف تکمیل می‌کند.
    """

    normalized_managers = _normalize_manager_overrides(manager_overrides)
    if mentors_df is None:
        empty = pd.DataFrame()
        empty.attrs["mentor_pool_governance"] = {
            "total": 0,
            "removed": 0,
            "manager_removed": 0,
            "overrides_count": len(_normalize_overrides(mentor_overrides)),
            "manager_overrides_count": len(normalized_managers),
        }
        if enable_trace:
            empty.attrs["mentor_pool_governance_trace"] = []
        return empty

    source = mentors_df.copy(deep=True)
    if source.empty:
        source.attrs["mentor_pool_governance"] = {
            "total": 0,
            "removed": 0,
            "manager_removed": 0,
            "overrides_count": len(_normalize_overrides(mentor_overrides)),
            "manager_overrides_count": len(normalized_managers),
        }
        if enable_trace:
            source.attrs["mentor_pool_governance_trace"] = []
        return source

    canonical = canonicalize_headers(source, header_mode="en")
    manager_col = "manager" if "manager" in canonical.columns else None
    if manager_col and normalized_managers:
        manager_series = canonical[manager_col].fillna("").map(str).str.strip()
        manager_mask = manager_series.map(lambda name: normalized_managers.get(name, True))
    else:
        manager_mask = pd.Series(True, index=canonical.index)

    filtered_managers = source.loc[manager_mask].copy()
    manager_removed = int((~manager_mask).sum())
    if filtered_managers.empty:
        filtered_managers.attrs["mentor_pool_governance"] = {
            "total": len(source),
            "removed": manager_removed,
            "manager_removed": manager_removed,
            "overrides_count": len(_normalize_overrides(mentor_overrides)),
            "manager_overrides_count": len(normalized_managers),
        }
        if enable_trace:
            filtered_managers.attrs["mentor_pool_governance_trace"] = []
        return filtered_managers

    governed = apply_mentor_pool_governance(
        filtered_managers,
        governance,
        overrides=mentor_overrides,
        enable_trace=enable_trace,
    )
    governed_attrs = governed.attrs.get("mentor_pool_governance", {})
    governed.attrs["mentor_pool_governance"] = {
        "total": len(source),
        "removed": manager_removed + int(governed_attrs.get("removed", 0)),
        "manager_removed": manager_removed,
        "overrides_count": governed_attrs.get(
            "overrides_count", len(_normalize_overrides(mentor_overrides))
        ),
        "manager_overrides_count": len(normalized_managers),
    }
    return governed
