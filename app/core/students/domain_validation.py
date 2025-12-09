"""Domain validation for student records (Core-only, deterministic)."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

from app.core.common.domain import allowed_statuses_for_group
from app.core.common.types import StudentDomainValidationIssue, StudentDomainValidationResult
from app.core.policy_loader import PolicyConfig

ERROR_INVALID_GRADUATION_FOR_GROUP = "INVALID_GRADUATION_FOR_GROUP"
ERROR_MISSING_GRADUATION_STATUS = "MISSING_GRADUATION_STATUS"
ERROR_MISSING_GROUP_CODE = "MISSING_GROUP_CODE"


def _safe_int(value: object) -> int | None:
    try:
        parsed = pd.to_numeric(value, errors="coerce")
    except Exception:
        return None
    if pd.isna(parsed):
        return None
    return int(parsed)


def validate_student_domain(
    df_students: pd.DataFrame,
    *,
    policy: PolicyConfig,
    progress: Callable[[int, str], None] | None = None,
) -> StudentDomainValidationResult:
    """Validate graduation-status domain against group/grade rules.

    The validation is non-raising and returns both canonical rows and
    structured issue records. It expects join keys to be canonicalized
    already (int columns as per Policy).
    """

    group_column = policy.stage_column("type")
    status_column = policy.stage_column("graduation_status")
    issues: list[StudentDomainValidationIssue] = []
    if progress:
        progress(0, "validating student domain")

    group_series = df_students.get(group_column)
    status_series = df_students.get(status_column)
    if group_series is None or status_series is None:
        raise KeyError("Student data missing required columns for domain validation")

    allowed_cache: dict[int, tuple[int, ...]] = {}
    valid_mask = pd.Series([True] * len(df_students), index=df_students.index)

    for row_index, (raw_group, raw_status) in enumerate(
        zip(group_series, status_series, strict=False)
    ):
        group_value = _safe_int(raw_group)
        status_value = _safe_int(raw_status)
        if group_value is None:
            issues.append(
                StudentDomainValidationIssue(
                    row_index=row_index,
                    group_code=None,
                    graduation_status=status_value,
                    allowed_statuses=tuple(),
                    error_code=ERROR_MISSING_GROUP_CODE,
                    severity="P0",
                )
            )
            valid_mask.iat[row_index] = False
            continue
        if status_value is None:
            issues.append(
                StudentDomainValidationIssue(
                    row_index=row_index,
                    group_code=group_value,
                    graduation_status=None,
                    allowed_statuses=tuple(),
                    error_code=ERROR_MISSING_GRADUATION_STATUS,
                    severity="P0",
                )
            )
            valid_mask.iat[row_index] = False
            continue

        if group_value not in allowed_cache:
            allowed_cache[group_value] = allowed_statuses_for_group(
                group_value, is_school_branch=False
            )
        allowed = allowed_cache[group_value]
        if status_value not in allowed:
            issues.append(
                StudentDomainValidationIssue(
                    row_index=row_index,
                    group_code=group_value,
                    graduation_status=status_value,
                    allowed_statuses=allowed,
                    error_code=ERROR_INVALID_GRADUATION_FOR_GROUP,
                    severity="P0",
                )
            )
            valid_mask.iat[row_index] = False

    canonical_df = df_students.loc[valid_mask].copy()
    canonical_df[status_column] = canonical_df[status_column].astype("Int64")
    canonical_df[group_column] = canonical_df[group_column].astype("Int64")
    if progress:
        progress(100, "student domain validation complete")
    return StudentDomainValidationResult(canonical_df=canonical_df, issues=issues)


def assert_student_domain_clean(df_students: pd.DataFrame, *, policy: PolicyConfig) -> None:
    """Raise ``ValueError`` if any student rows violate domain rules."""

    validation = validate_student_domain(df_students, policy=policy)
    if validation.issues:
        raise ValueError(
            "Student domain validation failed: " f"{len(validation.issues)} invalid rows detected"
        )
