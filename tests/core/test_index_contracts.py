from __future__ import annotations

import pandas as pd
import pytest

from app.core.common.contracts import (
    validate_allocation_output_contracts,
    validate_export_frame_contract,
)
from app.core.common.errors import ContractViolationError
from app.core.common.ranking import apply_ranking_policy
from app.core.policy_loader import load_policy


def _build_minimal_contract_payload() -> dict[str, pd.DataFrame]:
    allocations_df = pd.DataFrame(
        [
            {
                "student_id": "S-1",
                "student_national_code": "001",
                "mentor": "M-1",
                "mentor_id": "1",
                "mentor_alias_code": "",
            }
        ]
    )
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
    return {
        "allocations_df": allocations_df,
        "logs_df": logs_df,
        "trace_df": trace_df,
        "pool_internal": pool_internal,
    }


def test_export_contract_rejects_integer_label_trap() -> None:
    frame = pd.DataFrame({"value": [1, 2]}, index=pd.Index([10, 20]))

    with pytest.raises(ContractViolationError, match="integer index must be a strict RangeIndex"):
        validate_export_frame_contract(frame, context="unit-test")


def test_export_contract_rejects_non_range_index() -> None:
    frame = pd.DataFrame({"value": [1]}, index=pd.Index(["row-1"]))

    with pytest.raises(ContractViolationError, match="index must be a strict RangeIndex"):
        validate_export_frame_contract(frame, context="unit-test")


def test_allocation_contract_detects_new_pool_labels() -> None:
    policy = load_policy()
    payload = _build_minimal_contract_payload()
    pool_output = pd.DataFrame({key: [1, 1] for key in policy.join_keys})
    pool_with_ids = pd.DataFrame({key: [1] for key in policy.join_keys})

    with pytest.raises(ContractViolationError) as excinfo:
        validate_allocation_output_contracts(
            allocations_df=payload["allocations_df"],
            pool_output=pool_output,
            logs_df=payload["logs_df"],
            trace_df=payload["trace_df"],
            pool_internal=payload["pool_internal"],
            pool_with_ids=pool_with_ids,
            policy=policy,
        )

    codes = {issue.code for issue in excinfo.value.issues}
    assert "INDEX_NEW_LABELS" in codes


def test_allocation_contract_detects_new_labels_from_assignment() -> None:
    policy = load_policy()
    payload = _build_minimal_contract_payload()
    pool_output = pd.DataFrame({key: [1] for key in policy.join_keys})
    pool_with_ids = pool_output.copy()

    pool_output.loc[5, policy.join_keys[0]] = 1

    with pytest.raises(ContractViolationError) as excinfo:
        validate_allocation_output_contracts(
            allocations_df=payload["allocations_df"],
            pool_output=pool_output,
            logs_df=payload["logs_df"],
            trace_df=payload["trace_df"],
            pool_internal=payload["pool_internal"],
            pool_with_ids=pool_with_ids,
            policy=policy,
        )

    codes = {issue.code for issue in excinfo.value.issues}
    assert "INDEX_NEW_LABELS" in codes


def test_ranking_order_regression() -> None:
    policy = load_policy()
    pool = pd.DataFrame(
        [
            {"mentor_id": "B", "remaining_capacity": 2, "allocations_new": 0},
            {"mentor_id": "A", "remaining_capacity": 2, "allocations_new": 1},
            {"mentor_id": "C", "remaining_capacity": 1, "allocations_new": 0},
        ]
    )
    state = {
        "B": {"remaining": 2, "alloc_new": 0},
        "A": {"remaining": 2, "alloc_new": 1},
        "C": {"remaining": 1, "alloc_new": 0},
    }

    ranked = apply_ranking_policy(pool, policy=policy, state=state)

    assert ranked["mentor_id"].tolist() == ["B", "A", "C"]
