from __future__ import annotations

import pandas as pd

from app.infra.excel.export_allocations import collect_trace_debug_sheets


def test_bucket_trace_sheet_includes_skip_reason() -> None:
    trace_df = pd.DataFrame({"stage": ["type"]})
    logs_df = pd.DataFrame(
        {
            "student_id": ["s1"],
            "eligibility_trace": [
                {
                    "bucket_trace": {
                        "pool_built_size": 10,
                        "pool_size_before_bucket": 10,
                        "bucket_key": None,
                        "bucket_size": None,
                        "bucket_skip_reason": "disabled_by_setting",
                        "bucket_key_variants": [],
                        "bucket_sizes": [],
                    }
                }
            ],
        }
    )

    sheets = collect_trace_debug_sheets(
        trace_df,
        logs_df=logs_df,
        enable_bucket_trace=True,
        enable_standard_debug_sheets=False,
        enable_mentor_trace_debug=False,
        enable_history_metrics=False,
    )

    assert "BucketTrace" in sheets
    bucket_trace = sheets["BucketTrace"]
    assert bucket_trace.loc[0, "bucket_skip_reason"] == "disabled_by_setting"
