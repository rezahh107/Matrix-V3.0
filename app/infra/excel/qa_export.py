"""ساخت خروجی‌های QA تکمیلی برای مقایسهٔ کلیدهای join تخصیص."""

from __future__ import annotations

import pandas as pd

from app.core.policy_loader import PolicyConfig

__all__ = [
    "build_join_key_audit_sheet",
    "build_join_key_summary_sheet",
]


def build_join_key_audit_sheet(audit_df: pd.DataFrame, *, policy: PolicyConfig) -> pd.DataFrame:
    """آماده‌سازی شیت audit با ستون‌های هم‌ترازی دانش‌آموز و منتور.

    پارامترها
    ----------
    audit_df:
        دیتافریم خروجی اعتبارسنجی join keys که ستون‌های match_* دارد.
    policy:
        تنظیمات Policy برای دسترسی به لیست کلیدهای join.
    """

    if audit_df is None or audit_df.empty:
        columns = ["student_id", "mentor_id", "mentor_alias_code", *policy.join_keys]
        return pd.DataFrame(columns=columns)
    ordered_flags = [
        f"match_{col}" for col in policy.join_keys if f"match_{col}" in audit_df.columns
    ]
    preferred = [
        "student_id",
        "mentor_id",
        "mentor_alias_code",
        *policy.join_keys,
        *[f"{col}_mentor" for col in policy.join_keys if f"{col}_mentor" in audit_df.columns],
        *ordered_flags,
        "any_mismatch",
        "mismatch_summary",
    ]
    cols = [col for col in preferred if col in audit_df.columns]
    remaining = [col for col in audit_df.columns if col not in cols]
    result = audit_df.loc[:, cols + remaining].copy()
    if "any_mismatch" in result.columns:
        result = result.sort_values(
            by=["any_mismatch", "student_id"], ascending=[False, True], kind="stable"
        )
    return result


def build_join_key_summary_sheet(audit_df: pd.DataFrame) -> pd.DataFrame:
    """ساخت خلاصهٔ rule QA برای مغایرت‌های کلید join."""

    total = int(audit_df.shape[0]) if isinstance(audit_df, pd.DataFrame) else 0
    invalid = (
        int(audit_df["any_mismatch"].sum()) if total and "any_mismatch" in audit_df.columns else 0
    )
    data = [
        {
            "rule_id": "QA_RULE_ALLOC_JOIN_02",
            "passed": invalid == 0,
            "invalid_count": invalid,
            "total": total,
            "invalid_ratio": float(invalid) / float(total) if total else 0.0,
            "message": "per-student allocation vs pool join-key equality",
        }
    ]
    return pd.DataFrame(data)
