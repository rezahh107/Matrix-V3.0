from __future__ import annotations

import pandas as pd
from pandas.testing import assert_frame_equal

from app.infra.excel.export_allocations import collect_trace_debug_sheets


def test_collect_trace_debug_sheets_emits_join_key_provenance_counts() -> None:
    summary_df = pd.DataFrame(
        {
            "student_id": ["S-1", "S-2", "S-3"],
            "final_status": ["ALLOCATED", "ALLOCATED", "NO_ELIGIBLE_MENTOR"],
            "group_source": ["raw", "missing", "raw"],
            "gender_source": ["raw", "raw", "invalid"],
            "graduation_status_source": ["raw", "raw", "raw"],
            "center_source": ["manager_exact", "raw", "missing"],
            "finance_source": ["join_map", "missing", "invalid"],
            "school_source": ["defaulted_zero", "raw", "missing"],
        }
    )
    trace_df = pd.DataFrame({"student_id": summary_df["student_id"]})

    sheets = collect_trace_debug_sheets(
        trace_df,
        summary_df=summary_df,
        final_status_counts=summary_df["final_status"].value_counts(),
    )

    provenance = sheets["JoinKeyProvenance_counts"]
    expected = pd.DataFrame(
        [
            {
                "join_key_stage": "group",
                "join_key_column": "group",
                "inferred_count": 0,
                "defaulted_count": 1,
                "total_count": 3,
            },
            {
                "join_key_stage": "gender",
                "join_key_column": "gender",
                "inferred_count": 0,
                "defaulted_count": 1,
                "total_count": 3,
            },
            {
                "join_key_stage": "graduation_status",
                "join_key_column": "graduation_status",
                "inferred_count": 0,
                "defaulted_count": 0,
                "total_count": 3,
            },
            {
                "join_key_stage": "center",
                "join_key_column": "center",
                "inferred_count": 1,
                "defaulted_count": 1,
                "total_count": 3,
            },
            {
                "join_key_stage": "finance",
                "join_key_column": "finance",
                "inferred_count": 0,
                "defaulted_count": 2,
                "total_count": 3,
            },
            {
                "join_key_stage": "school",
                "join_key_column": "school",
                "inferred_count": 0,
                "defaulted_count": 2,
                "total_count": 3,
            },
        ]
    )
    assert_frame_equal(provenance.reset_index(drop=True), expected.reset_index(drop=True))
