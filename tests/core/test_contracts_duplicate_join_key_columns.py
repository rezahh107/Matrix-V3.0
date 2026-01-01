from __future__ import annotations

import pandas as pd
import pytest

from app.core.common.contracts import validate_allocation_output_contracts
from app.core.common.errors import ContractViolationError
from app.core.policy_loader import load_policy


def test_duplicate_join_key_columns_are_reported() -> None:
    policy = load_policy()
    join_keys = list(policy.join_keys)
    duplicate_columns = [join_keys[0], join_keys[0], *join_keys[1:]]

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
    pool_output = pd.DataFrame(
        [[1 for _ in duplicate_columns]],
        columns=duplicate_columns,
    )
    pool_with_ids = pd.DataFrame({key: [1] for key in join_keys})

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
    assert "SCHEMA_DUPLICATE_COLUMNS" in codes
    assert "JOIN_KEYS_DUPLICATE_COLUMN" in codes
