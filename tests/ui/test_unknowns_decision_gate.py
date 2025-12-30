from __future__ import annotations

from app.ui.dialogs.unknown_data_dialog import summarize_unknowns_report


def test_unknowns_report_summary_limits_samples() -> None:
    report = {
        "issues": [
            {
                "entity_type": "student",
                "row_index": 3,
                "column": "کدرشته",
                "raw_value": "x",
                "error_code": "DATA_INVALID",
            },
            {
                "entity_type": "pool",
                "row_index": 5,
                "column": "جنسیت",
                "raw_value": None,
                "error_code": "DATA_MISSING",
            },
        ]
    }
    summary = summarize_unknowns_report(report, sample_limit=1)
    assert summary.total == 2
    assert len(summary.samples) == 1
    assert summary.samples[0].row_index == 3
    assert summary.by_entity_type["student"] == 1
