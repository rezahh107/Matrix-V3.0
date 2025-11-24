"""اعتبارسنجی تطابق کلیدهای join بین تخصیص و استخر پشتیبان.

این ماژول صرفاً در لایهٔ Infra عمل می‌کند و هیچ منطق رتبه‌بندی یا تخصیص
جدیدی اضافه نمی‌کند؛ تنها از خروجی‌های Core (تخصیص و لاگ) و دادهٔ ورودی
استخر استفاده می‌کند تا گزارش QA و audit بسازد.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd

from app.core.common.columns import canonicalize_headers, ensure_series
from app.core.policy_loader import PolicyConfig

__all__ = [
    "JoinKeyAuditResult",
    "validate_allocation_join_keys",
]


@dataclass(frozen=True)
class JoinKeyAuditResult:
    """نتیجهٔ اعتبارسنجی per-student برای کلیدهای join.

    Attributes
    ----------
    audit_frame:
        دیتافریم شامل ستون‌های تطبیق دانش‌آموز/منتور و پرچم مغایرت.
    invalid_count:
        تعداد دانش‌آموزانی که حداقل یک مغایرت دارند.
    total:
        تعداد کل ردیف‌های تخصیص بررسی‌شده.
    """

    audit_frame: pd.DataFrame
    invalid_count: int
    total: int


def _pick_column(frame: pd.DataFrame, candidates: Sequence[str]) -> str | None:
    for name in candidates:
        if name in frame.columns:
            return name
    return None


def _prepare_join_keys(df: pd.DataFrame, columns: Sequence[str]) -> pd.DataFrame:
    coerced = df.copy()
    for column in columns:
        if column not in coerced.columns:
            coerced[column] = pd.Series([pd.NA] * len(coerced), index=coerced.index)
        coerced[column] = pd.to_numeric(coerced[column], errors="coerce").astype("Int64")
    return coerced


def validate_allocation_join_keys(
    allocations_df: pd.DataFrame,
    students_df: pd.DataFrame,
    pool_df: pd.DataFrame,
    *,
    policy: PolicyConfig,
) -> JoinKeyAuditResult:
    """بررسی برابری شش کلید join بین تخصیص و استخر.

    ورودی‌ها باید پیش‌تر توسط Core تولید شده باشند؛ این تابع فقط نام ستون‌ها را
    کاننیکال می‌کند، مقادیر را به int تبدیل می‌کند و پرچم مغایرت می‌سازد.

    مثال
    -----
    >>> result = validate_allocation_join_keys(alloc, students, pool, policy=policy)
    >>> result.invalid_count
    1
    >>> result.audit_frame.loc[0, "any_mismatch"]
    True
    """

    allocations = canonicalize_headers(allocations_df, header_mode="fa").copy()
    students = canonicalize_headers(students_df, header_mode="fa").copy()
    pool = canonicalize_headers(pool_df, header_mode="fa").copy()

    mentor_id_column = _pick_column(pool, ("mentor_id", "کد کارمندی پشتیبان"))
    alias_column = _pick_column(
        pool, ("mentor_alias_code", "جایگزین", "جایگزین | alias", "کدپستی", "کد پستی")
    )
    alloc_mentor_id_column = _pick_column(allocations, ("mentor_id", "کد کارمندی پشتیبان"))
    alloc_alias_column = _pick_column(
        allocations, ("mentor_alias_code", "کدپستی", "کد پستی", "alias")
    )

    if mentor_id_column is None and alias_column is None:
        return JoinKeyAuditResult(pd.DataFrame(), 0, int(allocations.shape[0]))

    student_columns = ["student_id", *policy.join_keys]
    student_subset = students.loc[
        :, [col for col in student_columns if col in students.columns]
    ].copy()
    student_subset = _prepare_join_keys(student_subset, policy.join_keys)

    mentor_keys = policy.join_keys
    mentor_subset = pool[[col for col in mentor_keys if col in pool.columns]].copy()
    mentor_subset = _prepare_join_keys(mentor_subset, mentor_keys)
    if mentor_id_column:
        mentor_subset["mentor_id"] = (
            ensure_series(pool[mentor_id_column]).astype("string").str.strip()
        )
    if alias_column and alias_column in pool.columns:
        mentor_subset["mentor_alias_code"] = (
            ensure_series(pool[alias_column]).astype("string").str.strip()
        )

    base = allocations.copy()
    if alloc_mentor_id_column:
        base["mentor_id"] = (
            ensure_series(allocations[alloc_mentor_id_column]).astype("string").str.strip()
        )
    if alloc_alias_column and alloc_alias_column in allocations.columns:
        base["mentor_alias_code"] = (
            ensure_series(allocations[alloc_alias_column]).astype("string").str.strip()
        )

    merged = base.merge(student_subset, on="student_id", how="left", suffixes=("", "_student"))
    mentor_merge_keys: list[str] = []
    if mentor_id_column and "mentor_id" in base.columns:
        mentor_merge_keys.append("mentor_id")
    if alias_column and "mentor_alias_code" in base.columns:
        mentor_merge_keys.append("mentor_alias_code")
    if mentor_merge_keys:
        merged = merged.merge(
            mentor_subset,
            on=mentor_merge_keys,
            how="left",
            suffixes=("", "_mentor"),
        )

    match_flags: dict[str, pd.Series] = {}
    for column in policy.join_keys:
        student_col = column
        mentor_col = f"{column}_mentor"
        if student_col in merged.columns and mentor_col in merged.columns:
            match_flags[f"match_{column}"] = (
                merged[student_col].notna()
                & merged[mentor_col].notna()
                & (merged[student_col] == merged[mentor_col])
            )
        else:
            match_flags[f"match_{column}"] = pd.Series([False] * len(merged), index=merged.index)

    audit = merged.copy()
    for name, series in match_flags.items():
        audit[name] = series
    mismatch_columns = [name for name in audit.columns if name.startswith("match_")]
    if mismatch_columns:
        audit["any_mismatch"] = ~pd.concat(match_flags.values(), axis=1).all(axis=1)
        audit["mismatch_summary"] = audit[mismatch_columns].apply(
            lambda row: ", ".join(col.replace("match_", "") for col, ok in row.items() if not ok),
            axis=1,
        )
    else:
        audit["any_mismatch"] = False
        audit["mismatch_summary"] = ""

    invalid_count = int(audit["any_mismatch"].sum()) if not audit.empty else 0
    return JoinKeyAuditResult(audit, invalid_count, int(audit.shape[0]))
