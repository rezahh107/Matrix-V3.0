"""Contract harness for core outputs and dataframe boundary checks."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

import pandas as pd
from pandas.api import types as pd_types

from app.core.common.errors import ContractIssue, ContractViolationError
from app.core.common.index_contract import assert_index_preserved, assert_no_new_labels
from app.core.common.isin_guard import isin_mask
from app.core.common.types import CANONICAL_TRACE_ORDER
from app.core.policy_loader import PolicyConfig

__all__ = [
    "validate_allocation_output_contracts",
    "validate_trace_contract",
    "validate_export_frame_contract",
]

_TRACE_STAGE_ORDER: Final[dict[str, int]] = {
    stage: idx for idx, stage in enumerate(CANONICAL_TRACE_ORDER)
}


def _is_strict_range_index(index: pd.Index) -> bool:
    if not isinstance(index, pd.RangeIndex):
        return False
    return bool(index.equals(pd.RangeIndex(len(index))))


def _issue(code: str, message: str, *, context: str | None = None) -> ContractIssue:
    return ContractIssue(code=code, message=message, context=context)


def _ensure_range_index(df: pd.DataFrame, *, context: str, issues: list[ContractIssue]) -> None:
    if _is_strict_range_index(df.index):
        return
    if pd_types.is_integer_dtype(df.index.dtype):
        issues.append(
            _issue(
                "INDEX_INTEGER_LABEL_TRAP",
                f"{context}: integer index must be a strict RangeIndex to avoid label traps.",
                context=context,
            )
        )
        return
    issues.append(
        _issue(
            "INDEX_NOT_RANGEINDEX",
            f"{context}: index must be a strict RangeIndex for deterministic exports.",
            context=context,
        )
    )


def _validate_schema(
    df: pd.DataFrame,
    *,
    required_columns: Sequence[str],
    context: str,
    issues: list[ContractIssue],
    allow_empty: bool = False,
) -> None:
    if not (allow_empty and df.empty):
        missing = [column for column in required_columns if column not in df.columns]
        if missing:
            issues.append(
                _issue(
                    "SCHEMA_MISSING_COLUMNS",
                    f"{context}: missing required columns: {missing}",
                    context=context,
                )
            )
    if not df.columns.is_unique:
        issues.append(
            _issue(
                "SCHEMA_DUPLICATE_COLUMNS",
                f"{context}: duplicate columns detected in output.",
                context=context,
            )
        )


def _validate_join_keys(
    df: pd.DataFrame,
    *,
    join_keys: Sequence[str],
    context: str,
    issues: list[ContractIssue],
) -> None:
    missing = [column for column in join_keys if column not in df.columns]
    if missing:
        issues.append(
            _issue(
                "JOIN_KEYS_MISSING",
                f"{context}: missing join-key columns: {missing}",
                context=context,
            )
        )
        return
    for column in join_keys:
        raw_values = df[column]
        if isinstance(raw_values, pd.DataFrame):
            issues.append(
                _issue(
                    "JOIN_KEYS_DUPLICATE_COLUMN",
                    f"{context}: join-key column '{column}' is duplicated; using first occurrence for validation.",
                    context=context,
                )
            )
            series = raw_values.iloc[:, 0]
        else:
            series = raw_values
        series = pd.to_numeric(series, errors="coerce")
        if series.isna().any():
            issues.append(
                _issue(
                    "JOIN_KEYS_NULL",
                    f"{context}: join-key column '{column}' has null/invalid values.",
                    context=context,
                )
            )
            continue
        remainder = series.astype("float").mod(1)
        if (remainder != 0).any():
            issues.append(
                _issue(
                    "JOIN_KEYS_NON_INT",
                    f"{context}: join-key column '{column}' must contain integers only.",
                    context=context,
                )
            )


def _validate_capacity_contract(
    pool_internal: pd.DataFrame,
    *,
    context: str,
    issues: list[ContractIssue],
) -> None:
    base_required = ("allocations_new", "remaining_capacity")
    missing = [column for column in base_required if column not in pool_internal.columns]
    if missing:
        issues.append(
            _issue(
                "CAPACITY_MISSING_COLUMNS",
                f"{context}: missing capacity columns: {missing}",
                context=context,
            )
        )
        return
    allocations_new = pd.to_numeric(pool_internal["allocations_new"], errors="coerce")
    remaining_capacity = pd.to_numeric(pool_internal["remaining_capacity"], errors="coerce")
    assigned_baseline = (
        pd.to_numeric(pool_internal["assigned_baseline"], errors="coerce")
        if "assigned_baseline" in pool_internal.columns
        else pd.Series([0] * len(pool_internal), index=pool_internal.index, dtype="int64")
    )
    capacity_limit = (
        pd.to_numeric(pool_internal["capacity_limit"], errors="coerce")
        if "capacity_limit" in pool_internal.columns
        else remaining_capacity.add(allocations_new, fill_value=0).add(
            assigned_baseline, fill_value=0
        )
    )
    if (
        capacity_limit.isna().any()
        or assigned_baseline.isna().any()
        or allocations_new.isna().any()
        or remaining_capacity.isna().any()
    ):
        issues.append(
            _issue(
                "CAPACITY_NON_NUMERIC",
                f"{context}: capacity columns must be numeric with no nulls.",
                context=context,
            )
        )
        return
    expected = capacity_limit.sub(assigned_baseline.add(allocations_new))
    if (expected < 0).any():
        issues.append(
            _issue(
                "CAPACITY_NEGATIVE_REMAINING",
                f"{context}: remaining_capacity would be negative for some rows.",
                context=context,
            )
        )
    if not expected.equals(remaining_capacity):
        issues.append(
            _issue(
                "CAPACITY_FORMULA_MISMATCH",
                f"{context}: remaining_capacity does not match capacity_limit - (assigned_baseline + allocations_new).",
                context=context,
            )
        )


def validate_trace_contract(
    trace_df: pd.DataFrame,
    *,
    context: str = "trace_df",
) -> None:
    """Validate trace shape and stage ordering."""
    issues: list[ContractIssue] = []
    _ensure_range_index(trace_df, context=context, issues=issues)
    _validate_schema(
        trace_df,
        required_columns=("student_id", "stage", "total_before", "total_after"),
        context=context,
        issues=issues,
        allow_empty=True,
    )
    if trace_df.empty:
        if issues:
            raise ContractViolationError(issues)
        return
    if "stage" in trace_df.columns:
        stage_series = trace_df["stage"].astype("string")
        unknown = stage_series[
            ~isin_mask(stage_series, _TRACE_STAGE_ORDER.keys(), name="trace_stage_order")
        ]
        if not unknown.empty:
            issues.append(
                _issue(
                    "TRACE_UNKNOWN_STAGE",
                    f"{context}: unexpected stage values detected: {sorted(unknown.unique())[:5]}",
                    context=context,
                )
            )
        stage_index = stage_series.map(_TRACE_STAGE_ORDER)
        if "student_id" in trace_df.columns and stage_index.notna().all():
            first_stage = CANONICAL_TRACE_ORDER[0]
            last_stage = CANONICAL_TRACE_ORDER[-1]
            for student_id, group in trace_df.groupby("student_id", sort=False):
                stages = stage_series.loc[group.index].tolist()
                indices = stage_index.loc[group.index].tolist()
                in_block = False
                prev_index_in_block: int | None = None
                prev_stage: str | None = None
                for stage_name, index_value in zip(stages, indices):
                    if stage_name == first_stage:
                        in_block = True
                        prev_index_in_block = index_value
                        prev_stage = stage_name
                        continue
                    if not in_block:
                        issues.append(
                            _issue(
                                "TRACE_STAGE_ORDER",
                                f"{context}: trace stages out of order for student_id={student_id!r}.",
                                context=context,
                            )
                        )
                        break
                    if prev_stage == last_stage and stage_name != first_stage:
                        issues.append(
                            _issue(
                                "TRACE_STAGE_ORDER",
                                f"{context}: trace stages out of order for student_id={student_id!r}.",
                                context=context,
                            )
                        )
                        break
                    if prev_index_in_block is not None and index_value < prev_index_in_block:
                        issues.append(
                            _issue(
                                "TRACE_STAGE_ORDER",
                                f"{context}: trace stages out of order for student_id={student_id!r}.",
                                context=context,
                            )
                        )
                        break
                    prev_index_in_block = index_value
                    prev_stage = stage_name
                if issues:
                    break
    if issues:
        raise ContractViolationError(issues)


def validate_export_frame_contract(
    frame: pd.DataFrame,
    *,
    context: str,
) -> None:
    """Validate generic DataFrame contracts before Excel/SQLite export."""
    issues: list[ContractIssue] = []
    _ensure_range_index(frame, context=context, issues=issues)
    if not frame.columns.is_unique:
        issues.append(
            _issue(
                "SCHEMA_DUPLICATE_COLUMNS",
                f"{context}: duplicate columns detected before export.",
                context=context,
            )
        )
    if issues:
        raise ContractViolationError(issues)


def validate_allocation_output_contracts(
    *,
    allocations_df: pd.DataFrame,
    pool_output: pd.DataFrame,
    logs_df: pd.DataFrame,
    trace_df: pd.DataFrame,
    pool_internal: pd.DataFrame,
    pool_with_ids: pd.DataFrame,
    policy: PolicyConfig,
) -> None:
    """Validate allocation outputs before returning from Core."""
    issues: list[ContractIssue] = []
    _ensure_range_index(allocations_df, context="allocations_df", issues=issues)
    _ensure_range_index(logs_df, context="logs_df", issues=issues)
    _ensure_range_index(trace_df, context="trace_df", issues=issues)
    _validate_schema(
        allocations_df,
        required_columns=(
            "student_id",
            "student_national_code",
            "mentor",
            "mentor_id",
            "mentor_alias_code",
        ),
        context="allocations_df",
        issues=issues,
    )
    _validate_schema(
        logs_df,
        required_columns=("student_id", "allocation_status"),
        context="logs_df",
        issues=issues,
        allow_empty=True,
    )
    _validate_schema(
        pool_output,
        required_columns=tuple(policy.join_keys),
        context="pool_output",
        issues=issues,
    )
    _validate_join_keys(
        pool_output,
        join_keys=tuple(policy.join_keys),
        context="pool_output",
        issues=issues,
    )
    _validate_capacity_contract(pool_internal, context="pool_internal", issues=issues)
    try:
        validate_trace_contract(trace_df, context="trace_df")
    except ContractViolationError as exc:
        issues.extend(list(exc.issues))
    try:
        assert_index_preserved(
            pool_with_ids.index,
            pool_internal.index,
            require_unique=True,
            require_same_order=True,
            context="pool_internal",
        )
    except ValueError as exc:
        issues.append(_issue("INDEX_POOL_INTERNAL_MISMATCH", str(exc), context="pool_internal"))
    try:
        assert_no_new_labels(
            pool_with_ids.index,
            pool_output.index,
            context="pool_output",
        )
    except ValueError as exc:
        issues.append(_issue("INDEX_NEW_LABELS", str(exc), context="pool_output"))
    if issues:
        raise ContractViolationError(issues)
