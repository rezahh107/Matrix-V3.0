"""اعتبارسنجی Join Key تخصیص با درنظرگرفتن wildcard مدرسه."""

from __future__ import annotations

import pandas as pd

from app.core.common.join_keys import matches_school_with_wildcard
from app.core.policy_loader import PolicyConfig
from app.infra.validators.join_keys import JoinKeyAuditResult, validate_allocation_join_keys

__all__ = ["validate_allocation_join_keys_with_wildcard"]


def validate_allocation_join_keys_with_wildcard(
    allocations_df: pd.DataFrame,
    students_df: pd.DataFrame,
    pool_df: pd.DataFrame,
    *,
    policy: PolicyConfig,
) -> JoinKeyAuditResult:
    """اجرای اعتبارسنجی Join Keys با تفسیر کد مدرسهٔ صفر به‌عنوان wildcard.

    این پوشش Infra نتایج پایهٔ `validate_allocation_join_keys` را دریافت می‌کند و
    در صورت فعال بودن سیاست `school_code_empty_as_zero`، مغایرت‌هایی را که تنها به
    دلیل صفر بودن یکی از طرفین ایجاد شده‌اند رفع می‌کند تا منتورهای «سراسری»
    به‌درستی منطبق شناخته شوند.
    """

    base_result: JoinKeyAuditResult = validate_allocation_join_keys(
        allocations_df, students_df, pool_df, policy=policy
    )
    if not policy.school_code_empty_as_zero:
        return base_result
    audit = base_result.audit_frame.copy()
    school_col = policy.columns.school_code
    match_column = f"match_{school_col}"
    if match_column not in audit.columns:
        return base_result
    constraint_column = "has_school_constraint"
    constraint_lookup: pd.DataFrame | None = None
    if constraint_column in pool_df.columns:
        constraint_lookup = pool_df[[constraint_column]].copy()
        if "mentor_id" in pool_df.columns:
            constraint_lookup["mentor_id"] = pool_df["mentor_id"].astype("string").str.strip()
        if "mentor_alias_code" in pool_df.columns:
            constraint_lookup["mentor_alias_code"] = (
                pool_df["mentor_alias_code"].astype("string").str.strip()
            )
    student_school = audit.get(school_col)
    mentor_school = audit.get(f"{school_col}_mentor")
    if student_school is None or mentor_school is None:
        return base_result
    if constraint_lookup is not None:
        merge_keys = [
            col
            for col in ("mentor_id", "mentor_alias_code")
            if col in audit.columns and col in constraint_lookup.columns
        ]
        if merge_keys:
            audit = audit.merge(constraint_lookup, on=merge_keys, how="left")
    fixed_flags: list[bool] = []
    constraints = audit.get(constraint_column)
    for s_val, m_val, flag, constraint in zip(
        student_school,
        mentor_school,
        audit[match_column],
        constraints if constraints is not None else [False] * len(audit),
    ):
        try:
            s_int = int(s_val)
            m_int = int(m_val)
        except Exception:
            fixed_flags.append(bool(flag))
            continue
        has_constraint = bool(constraint) if constraints is not None else True
        if (not has_constraint) or matches_school_with_wildcard(
            s_int, m_int, policy.school_code_empty_as_zero
        ):
            fixed_flags.append(True)
        else:
            fixed_flags.append(bool(flag))
    audit[match_column] = fixed_flags
    mismatch_columns = [name for name in audit.columns if name.startswith("match_")]
    if mismatch_columns:
        audit["any_mismatch"] = ~audit[mismatch_columns].all(axis=1)
    return JoinKeyAuditResult(
        audit_frame=audit,
        invalid_count=int(audit["any_mismatch"].sum()) if "any_mismatch" in audit.columns else 0,
        total=base_result.total,
        duplicate_columns=base_result.duplicate_columns,
    )
