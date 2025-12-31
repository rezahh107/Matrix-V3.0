from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.core.allocation.dedupe import HistoryStatus
from app.infra.config_flags import UserSettings, load_user_settings, save_user_settings
from app.infra.excel import export_allocations


def test_load_user_settings_defaults_when_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "user_settings.json"
    loaded = load_user_settings(missing_path)
    assert loaded == UserSettings()


def test_save_and_load_user_settings_roundtrip(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings = UserSettings(
        enable_history_metrics=True,
        enable_trace_debug_sheets=False,
        enable_trace_export=True,
        enable_mentor_trace_debug=True,
    )

    save_user_settings(settings, settings_path)
    raw = json.loads(settings_path.read_text(encoding="utf-8"))
    assert raw["enable_history_metrics"] is True

    loaded = load_user_settings(settings_path)
    assert loaded == settings


def test_user_settings_to_dict_is_limited_to_indicators() -> None:
    settings = UserSettings(
        enable_history_metrics=True,
        enable_trace_debug_sheets=True,
        enable_trace_export=False,
        enable_mentor_trace_debug=True,
    )

    settings_dict = settings.to_dict()

    assert settings_dict == {
        "enable_history_metrics": True,
        "enable_trace_debug_sheets": True,
        "enable_trace_export": False,
        "enable_mentor_trace_debug": True,
    }


def test_collect_trace_debug_sheets_respects_history_toggle() -> None:
    summary_payload: dict[str, list[object]] = {
        "student_id": [1],
        "allocation_channel": ["default"],
        "history_status": [HistoryStatus.ALREADY_ALLOCATED.value],
        "same_history_mentor": [True],
    }
    for column in export_allocations.JOIN_STAGE_SOURCE_KEYS.values():
        summary_payload[column] = ["default"]
    summary_df = pd.DataFrame(summary_payload)

    trace_df = pd.DataFrame({"stage": ["type"]})

    disabled = export_allocations.collect_trace_debug_sheets(
        trace_df,
        summary_df=summary_df,
        enable_history_metrics=False,
    )
    assert "HistoryMetrics" in disabled
    assert disabled["HistoryMetrics"].empty

    enabled = export_allocations.collect_trace_debug_sheets(
        trace_df,
        summary_df=summary_df,
        enable_history_metrics=True,
    )
    assert "HistoryMetrics" in enabled
    assert not enabled["HistoryMetrics"].empty


def test_collect_trace_debug_sheets_exports_eligibility_and_pipeline_trace() -> None:
    trace_df = pd.DataFrame({"stage": ["type"]})
    logs_df = pd.DataFrame(
        {
            "student_id": ["s1"],
            "eligibility_trace": [
                {
                    "initial": {"rows": 5},
                    "bucketed": {"rows": 3},
                    "eligible": {"rows": 2},
                    "preferred_count": 1,
                    "stage_counts": {"type": 5, "group": 3, "gender": 2},
                }
            ],
        }
    )
    pool_trace = [
        {"stage": "raw", "rows": 10, "columns": 7, "fingerprint": "abc123"}
    ]

    sheets = export_allocations.collect_trace_debug_sheets(
        trace_df,
        logs_df=logs_df,
        pool_trace=pool_trace,
        enable_mentor_trace_debug=True,
        enable_history_metrics=False,
    )

    assert "EligibilityTrace" in sheets
    eligibility = sheets["EligibilityTrace"]
    assert eligibility.loc[0, "initial_candidates"] == 5
    assert eligibility.loc[0, "bucketed_candidates"] == 3
    assert eligibility.loc[0, "eligible_candidates"] == 2
    assert eligibility.loc[0, "preferred_count"] == 1
    assert "stage_type_count" in eligibility.columns

    assert "MentorPipelineTrace" in sheets
    pipeline_df = sheets["MentorPipelineTrace"]
    assert list(pipeline_df["stage"]) == ["raw"]


def test_collect_trace_debug_sheets_off_returns_empty() -> None:
    trace_df = pd.DataFrame({"stage": ["type"]})

    sheets = export_allocations.collect_trace_debug_sheets(
        trace_df,
        enable_standard_debug_sheets=False,
        enable_mentor_trace_debug=False,
    )

    assert sheets == {}
