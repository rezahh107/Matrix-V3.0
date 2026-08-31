from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.core.policy_loader import load_policy
from app.infra.errors import JoinKeyValidationError
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.reference_students_repository import (
    import_student_report_from_excel,
    import_student_report_with_validation,
)
from app.infra.schools.school_repository import SchoolRepository


def _write_excel(df: pd.DataFrame, path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)


def _seed_references(db: LocalDatabase, tmp_path: Path) -> None:
    schools_path = tmp_path / "schools.xlsx"
    _write_excel(
        pd.DataFrame(
            {
                "کد مدرسه": [1001],
                "نام مدرسه": ["Synthetic School"],
                "مرکز گلستان صدرا": [1],
                "جنسیت": [1],
            }
        ),
        schools_path,
    )
    SchoolRepository(db).import_from_excel(schools_path)

    groups_path = tmp_path / "groupcodes.xlsx"
    _write_excel(
        pd.DataFrame(
            {
                "group_code": [1],
                "level": ["کنکوری"],
                "grade": [12],
                "track": ["ریاضی"],
            }
        ),
        groups_path,
    )
    GroupCodeRepository(db).import_from_excel(groups_path)


def test_invalid_group_code_surfaces_structured_result(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")
    _seed_references(db, tmp_path)
    raw = pd.DataFrame(
        {
            "student_id": ["s1"],
            "کدرشته": [""],
            "گروه آزمایشی": [""],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [1001],
        }
    )
    excel_path = tmp_path / "students.xlsx"
    _write_excel(raw, excel_path)

    bundle = import_student_report_with_validation(excel_path, db=db, policy=policy)

    assert len(bundle.join_keys.issues) == 1
    issue = bundle.join_keys.issues[0]
    assert issue.column == "کدرشته"
    assert issue.error_code == "DATA_MISSING"

    with pytest.raises(JoinKeyValidationError):
        import_student_report_from_excel(excel_path, db=db, policy=policy)


def test_valid_join_keys_pass_through(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "cache.sqlite")
    _seed_references(db, tmp_path)
    raw = pd.DataFrame(
        {
            "student_id": ["s1"],
            "کدرشته": [1],
            "گروه آزمایشی": ["تجربی"],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [1],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [1001],
            "کد ملی": ["001"],
        }
    )
    excel_path = tmp_path / "students.xlsx"
    _write_excel(raw, excel_path)

    bundle = import_student_report_with_validation(excel_path, db=db, policy=policy)

    assert not bundle.join_keys.issues
    assert not bundle.domain.issues
    assert "کدرشته" in bundle.canonical_df.columns
