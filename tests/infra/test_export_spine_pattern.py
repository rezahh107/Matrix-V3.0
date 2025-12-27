from __future__ import annotations

import pandas as pd
import pytest

from app.infra.cli_legacy import (
    AllocationConsistencyError,
    _build_allocations_view,
    _build_students_spine,
    _build_success_spine,
    _enforce_allocation_export_invariants,
)
from app.infra.excel.export_allocations import AllocationExportColumn, build_sabt_export_frame


def test_allocations_sabt_is_key_based_and_matches_logs_success() -> None:
    students = pd.DataFrame(
        {
            "student_id": ["S-1", "S-2", "S-3"],
            "کد ثبت نام0": [101, 102, 103],
            "نام": ["الف", "ب", "ج"],
        }
    )
    logs = pd.DataFrame(
        {
            "student_id": ["S-1", "S-2", "S-3"],
            "allocation_status": ["success", "failed", "success"],
            "mentor_id": [11, 12, 13],
        }
    )
    allocations = pd.DataFrame(
        {
            "student_id": ["S-3", "S-1", "S-2"],
            "mentor_id": [13, 11, 12],
        }
    )

    students_spine = _build_students_spine(students, header_mode="fa")
    success_spine = _build_success_spine(logs, students_spine=students_spine, header_mode="fa")
    allocations_view = _build_allocations_view(
        allocations, success_spine=success_spine, header_mode="fa"
    )

    profile = [
        AllocationExportColumn(
            key="registration_code",
            header="کد ثبت نام0",
            source_kind="student",
            source_field="کد ثبت نام0",
            literal_value=None,
            order=1,
        ),
        AllocationExportColumn(
            key="mentor_id",
            header="پیدا کردن ردیف پشتیبان از فیلد 141",
            source_kind="allocation",
            source_field="mentor_id",
            literal_value=None,
            order=2,
        ),
    ]

    sabt_allocations = build_sabt_export_frame(
        allocations_view, students_spine, profile, summary_df=None
    )

    sabt_ids = set(sabt_allocations["student_id"].tolist())
    assert sabt_ids == {"S-1", "S-3"}
    assert "S-2" not in sabt_allocations["student_id"].tolist()
    assert sabt_allocations["student_id"].tolist() == ["S-1", "S-3"]


def test_export_guard_blocks_on_overlap() -> None:
    allocations_df = pd.DataFrame({"student_id": ["S-1"], "mentor_id": [1]})
    logs_df = pd.DataFrame({"student_id": ["S-1"], "allocation_status": ["success"]})
    sabt_df = pd.DataFrame({"student_id": ["S-1"], "mentor_id": [1]})

    unallocated_summary = pd.DataFrame({"student_id": ["S-1"], "reason": ["NO_CAPACITY"]})

    with pytest.raises(AllocationConsistencyError, match="INV-EXPORT-02"):
        _enforce_allocation_export_invariants(
            allocations_df=allocations_df,
            logs_df=logs_df,
            join_key_audit=None,
            unallocated_summary=unallocated_summary,
            sabt_allocations_df=sabt_df,
        )

