"""Unit checks for Sabt export mapping."""

from __future__ import annotations

import pandas as pd

from app.infra.excel.export_allocations import (
    AllocationExportColumn,
    build_sabt_export_frame,
)


def test_educational_status_fallback_mapping() -> None:
    allocations = pd.DataFrame({"student_id": [1], "mentor_id": ["EMP-1"], "__source_index__": [0]})
    students = pd.DataFrame(
        {
            "student_id": [1],
            "student_educational_status": ["درحال تحصیل"],
            "__source_index__": [0],
        }
    )
    profile = [
        AllocationExportColumn(
            key="educational_status",
            header="وضعیت تحصیلی",
            source_kind="student",
            source_field="student_educational_status",
            literal_value=None,
            order=1,
        )
    ]

    export_df = build_sabt_export_frame(allocations, students, profile)

    assert export_df.loc[0, "وضعیت تحصیلی"] == "درحال تحصیل"


def test_empty_allocation_frame_exports_schema_only() -> None:
    allocations = pd.DataFrame(columns=["student_id", "mentor_id"])
    students = pd.DataFrame(
        {
            "student_id": ["S1"],
            "student_landline": ["021"],
        }
    )
    profile = [
        AllocationExportColumn(
            key="student_id",
            header="student_id",
            source_kind="allocation",
            source_field="student_id",
            literal_value=None,
            order=1,
        ),
        AllocationExportColumn(
            key="student_landline",
            header="تلفن منزل",
            source_kind="student",
            source_field="student_landline",
            literal_value=None,
            order=2,
        ),
    ]

    export_df = build_sabt_export_frame(allocations, students, profile)

    assert export_df.empty
    assert list(export_df.columns) == ["student_id", "تلفن منزل"]
