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
    )

    save_user_settings(settings, settings_path)
    raw = json.loads(settings_path.read_text(encoding="utf-8"))
    assert raw["enable_history_metrics"] is True

    loaded = load_user_settings(settings_path)
    assert loaded == settings


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
