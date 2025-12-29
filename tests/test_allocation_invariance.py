from __future__ import annotations

import pandas as pd
from pandas.testing import assert_frame_equal

from app.core.allocate_students import allocate_batch
from app.core.policy_adapter import policy as policy_adapter
from app.infra.config_flags import UserSettings
from app.infra.excel import export_allocations


def _build_sample_frames() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    capacity_column = policy_adapter.stage_column("capacity_gate")
    assert capacity_column is not None

    students = pd.DataFrame(
        [
            {
                "student_id": "STD-1",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
            },
            {
                "student_id": "STD-2",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
            },
        ]
    )

    candidate_pool = pd.DataFrame(
        [
            {
                "پشتیبان": "Mentor A",
                "کد کارمندی پشتیبان": "EMP-1",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
                capacity_column: 2,
                "allocations_new": 0,
                "mentor_sort_key": 1,
            }
        ]
    )

    return students, candidate_pool, capacity_column


def _select_columns(
    df: pd.DataFrame,
    preferred: list[str],
    *,
    exclude: set[str],
) -> list[str]:
    selected = [column for column in preferred if column in df.columns]
    if selected:
        return selected

    fallback = [column for column in df.columns if column not in exclude]
    return fallback or list(df.columns)


def _normalize_frame(
    df: pd.DataFrame,
    preferred: list[str],
    *,
    sort_keys: list[str],
    exclude: set[str],
) -> pd.DataFrame:
    columns = _select_columns(df, preferred, exclude=exclude)
    normalized = df[columns].copy()
    existing_sort_keys = [key for key in sort_keys if key in normalized.columns]
    if not existing_sort_keys:
        existing_sort_keys = list(normalized.columns)
    normalized = normalized.sort_values(existing_sort_keys).reset_index(drop=True)
    return normalized


def _run_allocation(settings: UserSettings) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    students, candidate_pool, capacity_column = _build_sample_frames()
    policy_config = policy_adapter.config

    batch_result = allocate_batch(
        students,
        candidate_pool,
        policy=policy_config,
        capacity_column=capacity_column,
    )

    if settings.enable_trace_debug_sheets:
        export_allocations.collect_trace_debug_sheets(
            batch_result.trace_df,
            summary_df=batch_result.trace_extras.summary_df,
            unallocated_summary=batch_result.trace_extras.unallocated_summary,
            policy_violations=batch_result.trace_extras.policy_violations,
            final_status_counts=batch_result.trace_extras.final_status_counts,
            enable_history_metrics=settings.enable_history_metrics,
        )

    allocations = _normalize_frame(
        batch_result.allocations_df,
        [
            "student_id",
            "student_national_code",
            "mentor",
            "mentor_id",
            "mentor_alias_code",
            "allocation_status",
            "mentor_selected",
            "school_id",
            "center_id",
            "track_id",
            "set_id",
            "choice_rank",
        ],
        sort_keys=["student_id", "mentor_id"],
        exclude=set(),
    )
    pool = _normalize_frame(
        batch_result.pool_output,
        [
            "mentor_id",
            capacity_column,
            "remaining_capacity",
            "allocations_new",
            "mentor_sort_key",
            "پشتیبان",
            "کد کارمندی پشتیبان",
            "occupancy_ratio",
        ],
        sort_keys=["mentor_id"],
        exclude={"join_keys", "join_key_sources"},
    )
    logs = _normalize_frame(
        batch_result.logs_df,
        [
            "student_id",
            "allocation_status",
            "mentor_selected",
            "mentor_id",
            "capacity_before",
            "capacity_after",
            "rule_reason_code",
            "fairness_reason_code",
        ],
        sort_keys=["student_id", "mentor_id"],
        exclude={
            "phase_rule_trace",
            "trace_stage_flags",
            "trace_final_status",
            "trace_failure_stage",
            "trace_final_reason",
            "join_keys",
            "join_key_sources",
            "alerts",
            "tie_breakers",
        },
    )

    return allocations, pool, logs


def test_allocation_invariant_with_toggles_on_vs_off() -> None:
    settings_off = UserSettings(
        enable_history_metrics=False,
        enable_trace_debug_sheets=False,
        enable_trace_export=False,
    )
    settings_on = UserSettings(
        enable_history_metrics=True,
        enable_trace_debug_sheets=True,
        enable_trace_export=True,
    )

    off_allocations, off_pool, off_logs = _run_allocation(settings_off)
    on_allocations, on_pool, on_logs = _run_allocation(settings_on)

    assert_frame_equal(off_allocations, on_allocations, check_dtype=False)
    assert_frame_equal(off_pool, on_pool, check_dtype=False)
    assert_frame_equal(off_logs, on_logs, check_dtype=False)


def test_allocation_deterministic_with_same_settings() -> None:
    settings = UserSettings(
        enable_history_metrics=False,
        enable_trace_debug_sheets=False,
        enable_trace_export=False,
    )

    first_allocations, first_pool, first_logs = _run_allocation(settings)
    second_allocations, second_pool, second_logs = _run_allocation(settings)

    assert_frame_equal(first_allocations, second_allocations, check_dtype=False)
    assert_frame_equal(first_pool, second_pool, check_dtype=False)
    assert_frame_equal(first_logs, second_logs, check_dtype=False)
