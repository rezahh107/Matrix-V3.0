from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.infra.db.reference_readiness import compute_reference_readiness
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository


def _write_excel(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)


def test_readiness_true_when_both_tables_populated(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    school_repo = SchoolRepository(db)
    groupcode_repo = GroupCodeRepository(db)

    schools_df = pd.DataFrame(
        {
            "کد مدرسه": [1, 2],
            "نام مدرسه": ["A", "B"],
            "مرکز گلستان صدرا": [10, 20],
            "جنسیت": [1, 2],
            "فعال": [1, 1],
        }
    )
    groupcodes_df = pd.DataFrame(
        {
            "group_code": [11, 22],
            "level": ["L1", "L2"],
            "grade": [1, 2],
            "track": ["T1", "T2"],
            "is_active": [1, 1],
        }
    )
    schools_path = tmp_path / "schools.xlsx"
    groupcodes_path = tmp_path / "groupcodes.xlsx"
    _write_excel(schools_df, schools_path)
    _write_excel(groupcodes_df, groupcodes_path)

    school_repo.import_from_excel(schools_path)
    groupcode_repo.import_from_excel(groupcodes_path)

    readiness = compute_reference_readiness(school_repo=school_repo, groupcode_repo=groupcode_repo)

    assert readiness.schools_ready is True
    assert readiness.groupcodes_ready is True
    assert readiness.is_ready_for_run is True
    assert readiness.schools.row_count == 2
    assert readiness.groupcodes.row_count == 2


def test_readiness_false_when_groupcodes_missing(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    school_repo = SchoolRepository(db)
    groupcode_repo = GroupCodeRepository(db)

    schools_df = pd.DataFrame(
        {
            "کد مدرسه": [1],
            "نام مدرسه": ["Only"],
            "مرکز گلستان صدرا": [10],
            "جنسیت": [1],
            "فعال": [1],
        }
    )
    schools_path = tmp_path / "schools.xlsx"
    _write_excel(schools_df, schools_path)

    school_repo.import_from_excel(schools_path)

    readiness = compute_reference_readiness(school_repo=school_repo, groupcode_repo=groupcode_repo)

    assert readiness.schools_ready is True
    assert readiness.groupcodes_ready is False
    assert readiness.is_ready_for_run is False
    assert readiness.groupcodes.row_count == 0


def test_readiness_false_on_zero_row_import(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    school_repo = SchoolRepository(db)
    groupcode_repo = GroupCodeRepository(db)

    empty_groupcodes = pd.DataFrame(
        {
            "group_code": pd.Series(dtype="Int64"),
            "level": pd.Series(dtype="string"),
            "grade": pd.Series(dtype="Int64"),
            "track": pd.Series(dtype="string"),
        }
    )
    empty_path = tmp_path / "empty_groupcodes.xlsx"
    _write_excel(empty_groupcodes, empty_path)

    groupcode_repo.import_from_excel(empty_path)

    readiness = compute_reference_readiness(school_repo=school_repo, groupcode_repo=groupcode_repo)

    assert readiness.groupcodes_ready is False
    assert readiness.is_ready_for_run is False
    assert readiness.groupcodes.row_count == 0
