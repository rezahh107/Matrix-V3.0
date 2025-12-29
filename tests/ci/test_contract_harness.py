from __future__ import annotations

import pandas as pd
import pytest

from app.core import allocate_students
from app.core.common.contracts import validate_allocation_output_contracts, validate_trace_contract
from app.core.common.errors import ContractViolationError
from app.core.policy_loader import load_policy


def test_contract_harness_rejects_non_range_index() -> None:
    policy = load_policy()
    allocations_df = pd.DataFrame(
        [
            {
                "student_id": "S-1",
                "student_national_code": "001",
                "mentor": "M-1",
                "mentor_id": "1",
                "mentor_alias_code": "",
            }
        ],
        index=pd.Index([10]),
    )
    pool_output = pd.DataFrame({key: [1] for key in policy.join_keys})
    logs_df = pd.DataFrame([{"student_id": "S-1", "allocation_status": "success"}])
    trace_df = pd.DataFrame(
        [
            {
                "student_id": "S-1",
                "stage": "type",
                "total_before": 1,
                "total_after": 1,
            }
        ]
    )
    pool_internal = pd.DataFrame(
        {
            "capacity_limit": [1],
            "assigned_baseline": [0],
            "allocations_new": [0],
            "remaining_capacity": [1],
        }
    )
    pool_with_ids = pool_output.copy()

    with pytest.raises(ContractViolationError) as excinfo:
        validate_allocation_output_contracts(
            allocations_df=allocations_df,
            pool_output=pool_output,
            logs_df=logs_df,
            trace_df=trace_df,
            pool_internal=pool_internal,
            pool_with_ids=pool_with_ids,
            policy=policy,
        )

    codes = {issue.code for issue in excinfo.value.issues}
    assert "INDEX_INTEGER_LABEL_TRAP" in codes or "INDEX_NOT_RANGEINDEX" in codes


def test_allocate_batch_invokes_output_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = load_policy()
    capacity_column = policy.stage_column("capacity_gate")
    assert capacity_column is not None

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

    def _raise_gateway(*_: object, **__: object) -> object:
        raise RuntimeError("gateway-called")

    monkeypatch.setattr(allocate_students, "enforce_allocation_output_contracts", _raise_gateway)

    with pytest.raises(RuntimeError, match="gateway-called"):
        allocate_students.allocate_batch(students, pool, policy=policy)


def test_trace_contract_rejects_out_of_order_stages() -> None:
    trace_df = pd.DataFrame(
        [
            {"student_id": "S-1", "stage": "group", "total_before": 1, "total_after": 1},
            {"student_id": "S-1", "stage": "type", "total_before": 1, "total_after": 1},
        ]
    )

    with pytest.raises(ContractViolationError, match="trace stages out of order"):
        validate_trace_contract(trace_df, context="unit-test")


def test_trace_contract_allows_repeated_blocks() -> None:
    trace_df = pd.DataFrame(
        [
            {"student_id": "S-1", "stage": "type", "total_before": 1, "total_after": 1},
            {"student_id": "S-1", "stage": "group", "total_before": 1, "total_after": 1},
            {"student_id": "S-1", "stage": "capacity_gate", "total_before": 1, "total_after": 1},
            {"student_id": "S-1", "stage": "type", "total_before": 1, "total_after": 1},
            {"student_id": "S-1", "stage": "group", "total_before": 1, "total_after": 1},
            {"student_id": "S-1", "stage": "capacity_gate", "total_before": 1, "total_after": 1},
        ]
    )

    validate_trace_contract(trace_df, context="unit-test")


def test_trace_contract_rejects_continuation_after_last_stage() -> None:
    trace_df = pd.DataFrame(
        [
            {"student_id": "S-1", "stage": "type", "total_before": 1, "total_after": 1},
            {"student_id": "S-1", "stage": "capacity_gate", "total_before": 1, "total_after": 1},
            {"student_id": "S-1", "stage": "school", "total_before": 1, "total_after": 1},
        ]
    )

    with pytest.raises(ContractViolationError, match="trace stages out of order"):
        validate_trace_contract(trace_df, context="unit-test")
