from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.infra.excel.export_allocations import (
    SABT_PROFILE_RULE_ID,
    AllocationExportColumn,
    ProfileMappingIssue,
    build_profile_mapping_rule_result,
    build_sabt_export_frame,
)


def _base_allocations() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "student_id": [1, 2],
            "mentor_id": [101, 102],
            "__source_index__": [0, 1],
        }
    )


def _base_students() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "student_id": [1, 2],
            "student_landline": ["02111111111", "02122222222"],
            "__source_index__": [0, 1],
        }
    )


def test_invalid_profile_mapping_emits_issue_and_marks_export_blank() -> None:
    allocations_df = _base_allocations()
    students_df = _base_students()
    profile = [
        AllocationExportColumn(
            key="student_id",
            header="کد ثبت نام",
            source_kind="allocation",
            source_field="student_id",
            literal_value=None,
            order=1,
        ),
        AllocationExportColumn(
            key="student_landline",
            header="تلفن منزل",
            source_kind="student",
            source_field="تلفن منزل (اشتباه)",
            literal_value=None,
            order=2,
            mapping_hint="تلفن منزل (اشتباه)",
            profile_path=Path("/tmp/profile.xlsx"),
            profile_row=5,
        ),
    ]

    export_df = build_sabt_export_frame(
        allocations_df,
        students_df,
        profile,
        profile_path=Path("/tmp/profile.xlsx"),
    )

    issues = export_df.attrs.get("profile_mapping_issues") or []
    assert len(issues) == 1
    issue = issues[0]
    assert isinstance(issue, ProfileMappingIssue)
    assert issue.output_column_name == "تلفن منزل"
    assert issue.referenced_source_field == "تلفن منزل (اشتباه)"
    assert issue.dataset_frame_expected == "students"
    assert issue.profile_path and str(issue.profile_path).endswith("profile.xlsx")
    assert export_df["تلفن منزل"].isna().all()

    rule = build_profile_mapping_rule_result(issues)
    assert rule is not None
    assert rule.rule_id == SABT_PROFILE_RULE_ID
    assert rule.passed
    assert rule.violations and rule.violations[0].details["output_column_name"] == "تلفن منزل"


def test_valid_profile_mapping_populates_data_and_has_no_issue() -> None:
    allocations_df = _base_allocations()
    students_df = _base_students()
    profile = [
        AllocationExportColumn(
            key="student_id",
            header="کد ثبت نام",
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

    export_df = build_sabt_export_frame(
        allocations_df,
        students_df,
        profile,
        profile_path=Path("/tmp/profile.xlsx"),
    )

    issues = export_df.attrs.get("profile_mapping_issues") or []
    assert issues == []
    assert export_df["تلفن منزل"].tolist() == ["02111111111", "02122222222"]
