from __future__ import annotations

import pandas as pd

from app.infra.excel.export_allocations import collect_trace_debug_sheets
from app.infra.reference_mentors_repository import _POOL_QA_PAYLOAD_ATTR


def test_pool_condense_trace_reports_profiles() -> None:
    trace_df = pd.DataFrame({"stage": ["type"]})
    pool_df = pd.DataFrame({"mentor_id": ["m1", "m2"], "remaining_capacity": [1, 1]})
    pool_df.attrs[_POOL_QA_PAYLOAD_ATTR] = {
        "all_profiles": [
            {"mentor_id": "m1"},
            {"mentor_id": "m1"},
            {"mentor_id": "m2"},
        ]
    }

    sheets = collect_trace_debug_sheets(
        trace_df,
        pool_df=pool_df,
        enable_pool_governance_trace=True,
        enable_standard_debug_sheets=False,
        enable_mentor_trace_debug=False,
        enable_history_metrics=False,
    )

    assert "PoolCondenseTrace" in sheets
    condense = sheets["PoolCondenseTrace"].iloc[0]
    assert condense["profile_rows_before"] == 3
    assert condense["unique_mentor_ids_before"] == 2
    assert condense["profile_rows_after"] == 2

    assert "MultiProfileSummary" in sheets
    summary = sheets["MultiProfileSummary"].iloc[0]
    assert summary["multi_profile_mentor_count"] == 1
