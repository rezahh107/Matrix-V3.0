from __future__ import annotations

import pandas as pd

from app.infra.excel.export_allocations import AllocationExportColumn, build_sabt_export_frame


def test_sabt_export_uses_fallback_for_gender_and_educational_status() -> None:
    allocation_df = pd.DataFrame(
        {
            "student_id": ["S-1"],
            "mentor_id": [101],
            "mentor_alias_code": ["A-1"],
        }
    )
    students_df = pd.DataFrame(
        {
            "student_id": ["S-1"],
            "gender": [1],
            "دانش آموز فارغ": [0],
        }
    )

    profile = [
        AllocationExportColumn(
            key="gender",
            header="جنسیت",
            source_kind="student",
            source_field="جنسیت",
            literal_value=None,
            order=1,
        ),
        AllocationExportColumn(
            key="educational_status",
            header="وضعیت تحصیلی",
            source_kind="student",
            source_field="student_educational_status",
            literal_value=None,
            order=2,
        ),
    ]

    result = build_sabt_export_frame(allocation_df, students_df, profile)

    assert result.loc[0, "جنسیت"] == 1
    assert result.loc[0, "وضعیت تحصیلی"] == 0
    assert result.attrs["missing_student_columns"] == []
