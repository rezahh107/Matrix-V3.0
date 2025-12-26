"""اعتبارسنجی Join Key تخصیص با درنظرگرفتن wildcard مدرسه."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import pandas as pd

from app.core.common.join_keys import (
    center_wildcard_value,
    finance_variants_from_cell,
    matches_center_with_wildcard,
    matches_school_with_wildcard,
    resolve_finance_variants,
)
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
    audit = base_result.audit_frame.copy()
    school_col = policy.columns.school_code
    center_col = policy.stage_column("center")
    finance_col = policy.stage_column("finance")
    wildcard_center = center_wildcard_value(policy)

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

    if constraint_lookup is not None:
        merge_keys = [
            col
            for col in ("mentor_id", "mentor_alias_code")
            if col in audit.columns and col in constraint_lookup.columns
        ]
        if merge_keys:
            audit = audit.merge(constraint_lookup, on=merge_keys, how="left")

    def _fix_match_column(
        column: str,
        mentor_column: str,
        matcher: Callable[[int, int, object], bool],
        constraint_series: pd.Series | None = None,
    ) -> None:
        match_column = f"match_{column}"
        if match_column not in audit.columns:
            return
        student_series = audit.get(column)
        mentor_series = audit.get(mentor_column)
        if student_series is None or mentor_series is None:
            return
        fixed: list[bool] = []
        constraints_iterable: Iterable[object]
        if constraint_series is not None:
            constraints_iterable = constraint_series
        else:
            constraints_iterable = [None] * len(audit)
        for student_value, mentor_value, base_flag, constraint_value in zip(
            student_series, mentor_series, audit[match_column], constraints_iterable
        ):
            try:
                student_int = int(student_value)
                mentor_int = int(mentor_value)
            except Exception:
                fixed.append(bool(base_flag))
                continue
            fixed.append(matcher(student_int, mentor_int, constraint_value))
        audit[match_column] = fixed

    school_constraint = audit.get(constraint_column)

    def _school_matcher(student_value: int, mentor_value: int, constraint_value: object) -> bool:
        if constraint_value is None:
            has_constraint = True
        else:
            try:
                has_constraint = bool(constraint_value)
            except Exception:
                has_constraint = True
        if not has_constraint:
            return True
        allow_empty_as_zero = (
            policy.school_code_empty_as_zero or student_value == 0 or mentor_value == 0
        )
        return matches_school_with_wildcard(student_value, mentor_value, allow_empty_as_zero)

    _fix_match_column(
        school_col,
        f"{school_col}_mentor",
        _school_matcher,
        constraint_series=school_constraint if school_constraint is not None else None,
    )
    _fix_match_column(
        center_col,
        f"{center_col}_mentor",
        lambda student_value, mentor_value, _constraint: matches_center_with_wildcard(
            student_value, mentor_value, wildcard_center
        ),
    )
    _fix_match_column(
        finance_col,
        f"{finance_col}_mentor",
        lambda student_value, mentor_value, _constraint: bool(
            resolve_finance_variants(student_value, policy).intersection(
                finance_variants_from_cell(mentor_value, policy)
            )
        ),
    )

    mismatch_columns = [name for name in audit.columns if name.startswith("match_")]
    if mismatch_columns:
        audit["any_mismatch"] = ~audit[mismatch_columns].all(axis=1)
        audit["mismatch_summary"] = audit[mismatch_columns].apply(
            lambda row: ", ".join(col.replace("match_", "") for col, ok in row.items() if not ok),
            axis=1,
        )
    return JoinKeyAuditResult(
        audit_frame=audit,
        invalid_count=int(audit["any_mismatch"].sum()) if "any_mismatch" in audit.columns else 0,
        total=base_result.total,
        duplicate_columns=base_result.duplicate_columns,
    )
