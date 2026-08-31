from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.excel.import_students import import_students_with_validation
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository


def _prepare_reference_db(tmp_path: Path) -> LocalDatabase:
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
            "group_code": [1, 33],
            "level": ["کنکوری", "متوسطه اول"],
            "grade": [12, 7],
            "track": ["ریاضی", "عمومی"],
            "is_active": [1, 1],
        }
    ).to_excel(groupcodes_ref, index=False)
    GroupCodeRepository(db).import_from_excel(groupcodes_ref)
    return db


def test_reference_students_repo_applies_domain_validation(tmp_path: Path) -> None:
    policy = load_policy()
    df = pd.DataFrame(
        [
            {
                "کدرشته": 1,
                "جنسیت": 1,
                "دانش آموز فارغ": 0,
                "مرکز گلستان صدرا": 2,
                "مالی حکمت بنیاد": 1,
                "کد مدرسه": 10,
            },
            {
                "کدرشته": 33,
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
    db = _prepare_reference_db(tmp_path)
    result = import_students_with_validation(csv_path, db=db, policy=policy)
    assert len(result.canonical_df) == 1
    assert result.domain.issues


def test_domain_issues_persisted_to_cache(tmp_path: Path) -> None:
    policy = load_policy()
    df = pd.DataFrame(
        {
            "کدرشته": [33],
            "جنسیت": [1],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [2],
            "مالی حکمت بنیاد": [1],
            "کد مدرسه": [10],
        }
    )
    csv_path = tmp_path / "students.csv"
    df.to_csv(csv_path, index=False)
    db = _prepare_reference_db(tmp_path)
    result = import_students_with_validation(csv_path, db=db, policy=policy)
    cached = result.canonical_df
    assert cached.empty
    # join-key issues are independent from domain issues
    assert not result.join_keys.issues
