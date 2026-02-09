from __future__ import annotations

import pandas as pd

from app.infra.excel.export_allocations import AllocationExportColumn, build_sabt_export_frame


def test_sabt_export_normalizes_national_code_with_leading_zero() -> None:
    allocations_df = pd.DataFrame(
        [
            {
                "student_id": "S-1",
                "mentor_id": "M-1",
                "student_national_code": 250188279,
                "__source_index__": 0,
            }
        ]
    )
    students_df = pd.DataFrame(
        [
            {
                "student_id": "S-1",
                "student_national_code": 250188279,
                "__source_index__": 0,
            }
        ]
    )
    profile = [
        AllocationExportColumn(
            key="student_national_code",
            header="کد ملی",
            source_kind="student",
            source_field="student_national_code",
            literal_value=None,
            order=1,
        ),
        AllocationExportColumn(
            key="student_id",
            header="شناسه",
            source_kind="allocation",
            source_field="student_id",
            literal_value=None,
            order=2,
        ),
    ]

    export_df = build_sabt_export_frame(allocations_df, students_df, profile)

    assert export_df.loc[0, "کد ملی"] == "0250188279"
