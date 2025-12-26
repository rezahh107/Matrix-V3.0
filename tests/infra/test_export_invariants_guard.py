from __future__ import annotations

import pandas as pd
import pytest

from app.infra.cli_legacy import AllocationConsistencyError, _enforce_allocation_export_invariants
from app.infra.validators.join_keys import JoinKeyAuditResult


def test_export_invariants_fail_on_join_key_invalid_count() -> None:
    allocations_df = pd.DataFrame({"student_id": ["S-1"], "mentor_id": [1]})
    logs_df = pd.DataFrame({"student_id": ["S-1"], "allocation_status": ["success"]})

    audit_frame = pd.DataFrame(
        {
            "student_id": ["S-1"],
            "any_mismatch": [True],
        }
    )
    join_key_audit = JoinKeyAuditResult(total=1, invalid_count=1, audit_frame=audit_frame, duplicate_columns=set())

    with pytest.raises(AllocationConsistencyError, match="INV-QA-ALLOC-JOIN-02"):
        _enforce_allocation_export_invariants(
            allocations_df=allocations_df,
            logs_df=logs_df,
            join_key_audit=join_key_audit,
            unallocated_summary=None,
        )


def test_export_invariants_fail_on_allocations_unallocated_overlap() -> None:
    allocations_df = pd.DataFrame({"student_id": ["S-1"], "mentor_id": [1]})
    logs_df = pd.DataFrame({"student_id": ["S-1"], "allocation_status": ["success"]})

    unallocated_summary = pd.DataFrame({"student_id": ["S-1"], "reason": ["NO_CAPACITY"]})

    with pytest.raises(AllocationConsistencyError, match="INV-EXPORT-02"):
        _enforce_allocation_export_invariants(
            allocations_df=allocations_df,
            logs_df=logs_df,
            join_key_audit=None,
            unallocated_summary=unallocated_summary,
        )
