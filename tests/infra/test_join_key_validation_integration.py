from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.excel.import_students import import_students_with_validation
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository


def test_student_import_validation(tmp_path: Path) -> None:
    policy = load_policy()
    df = pd.DataFrame(
        [
            {
                "کدرشته": "1",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
            {
                "کدرشته": "",
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
        ]
    )
    csv_path = tmp_path / "students.csv"
    df.to_csv(csv_path, index=False)

    db = LocalDatabase(tmp_path / "db.sqlite")
    schools_ref = tmp_path / "schools.xlsx"
    pd.DataFrame(
        {
            "کد مدرسه": [10],
            "نام مدرسه": ["Synthetic School"],
            "مرکز گلستان صدرا": [2],
            "جنسیت": [1],
            "فعال": [1],
        }
    ).to_excel(schools_ref, index=False)
    SchoolRepository(db).import_from_excel(schools_ref)

    groupcodes_ref = tmp_path / "groupcodes.xlsx"
    pd.DataFrame(
        {
            "group_code": [1],
            "level": ["متوسطه دوم"],
            "grade": [12],
            "track": ["تجربی"],
            "is_active": [1],
        }
    ).to_excel(groupcodes_ref, index=False)
    GroupCodeRepository(db).import_from_excel(groupcodes_ref)

    result = import_students_with_validation(csv_path, db=db, policy=policy)
    assert len(result.canonical_df) == 1
    assert result.join_keys.issues
