from __future__ import annotations

import inspect

import pandas as pd

from app.core.pipeline import enrich_student_contacts
from app.infra.excel.export_allocations import (
    AllocationExportColumn,
    build_sabt_export_frame,
)
from app.infra.excel.import_to_sabt import build_sheet2_frame


def test_sabt_export_preserves_landline_pass_through() -> None:
    allocations_df = pd.DataFrame(
        [
            {
                "student_id": "STU-1",
                "mentor_id": "MENTOR-1",
                "__source_index__": 0,
            },
            {
                "student_id": "STU-2",
                "mentor_id": "MENTOR-2",
                "__source_index__": 1,
            },
        ]
    )

    students_df = pd.DataFrame(
        [
            {
                "student_id": "STU-1",
                "student_landline": "05131234567",
                "student_mobile": "09123456789",
                "student_registration_status": 0,
                "__source_index__": 0,
            },
            {
                "student_id": "STU-2",
                "student_landline": "",
                "student_mobile": "09120000000",
                "student_registration_status": 3,
                "__source_index__": 1,
            },
        ]
    )

    sabt_profile = [
        AllocationExportColumn(
            key="student_id",
            header="شناسه دانش آموز",
            source_kind="allocation",
            source_field="student_id",
            literal_value=None,
            order=1,
        ),
        AllocationExportColumn(
            key="student_landline",
            header="تلفن منزل",
            source_kind="student",
            source_field="تلفن ثابت",
            literal_value=None,
            order=2,
        ),
    ]

    export_df = build_sabt_export_frame(
        allocations_df,
        students_df,
        sabt_profile,
    )

    assert export_df.loc[0, "تلفن منزل"] == "05131234567"
    assert export_df.loc[1, "تلفن منزل"] == "00000000000"


def test_landline_normalization_not_reintroduced() -> None:
    source_enrich = inspect.getsource(enrich_student_contacts)
    source_sheet2 = inspect.getsource(build_sheet2_frame)

    assert "normalize_landline_series" not in source_enrich
    assert "normalize_landline_series" not in source_sheet2
