from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.core.allocate_students import allocate_batch
from app.core.policy_loader import load_policy
from app.infra.history_store import build_run_context, log_allocation_run
from app.infra.local_database import LocalDatabase


def _build_inputs() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    policy = load_policy()
    capacity_column = policy.stage_column("capacity_gate")
    if capacity_column is None:
        raise RuntimeError("Policy missing capacity_gate column")
    students = pd.DataFrame(
        [
            {
                "student_id": "S-1",
                "کدرشته": 1,
                "گروه آزمایشی": "تجربی",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 0,
                "مالی حکمت بنیاد": 0,
                "کد مدرسه": 1010,
            }
        ]
    )
    pool = pd.DataFrame(
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
                capacity_column: 1,
                "occupancy_ratio": 0.1,
                "allocations_new": 0,
                "mentor_sort_key": 1,
            }
        ]
    )
    return students, pool, capacity_column


def test_history_store_failure_does_not_mutate_allocation_results(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    students, pool, _ = _build_inputs()
    result = allocate_batch(students, pool)

    allocations_before = result.allocations_df.copy(deep=True)
    pool_before = result.pool_output.copy(deep=True)
    logs_before = result.logs_df.copy(deep=True)
    trace_before = result.trace_df.copy(deep=True)

    db = LocalDatabase(tmp_path / "history.db")

    def _raise_initialize() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(db, "initialize", _raise_initialize)

    now = datetime.now(tz=UTC)
    ctx = build_run_context(
        command="unit-test",
        cli_args=None,
        policy_version="test",
        ssot_version="1.0.2",
        started_at=now,
        completed_at=now,
        success=True,
        message="ok",
        input_students=None,
        input_pool=None,
        output=None,
        policy_path=None,
        total_students=len(students),
        allocated_students=len(result.allocations_df),
        unallocated_students=0,
    )

    log_allocation_run(
        run_uuid="run-1",
        ctx=ctx,
        history_metrics=None,
        qa_outcome=None,
        qa_report=None,
        trace_snapshot=result.trace_df,
        trace_summary_df=result.trace_extras.summary_df,
        qa_extras=None,
        db=db,
    )

    pd.testing.assert_frame_equal(allocations_before, result.allocations_df)
    pd.testing.assert_frame_equal(pool_before, result.pool_output)
    pd.testing.assert_frame_equal(logs_before, result.logs_df)
    pd.testing.assert_frame_equal(trace_before, result.trace_df)
