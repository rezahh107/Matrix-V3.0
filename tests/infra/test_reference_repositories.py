from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.core.common.columns import canonicalize_headers
from app.infra.errors import DatabasePreparationError
from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.io_utils import read_excel_first_sheet
from app.infra.local_database import LocalDatabase
from app.infra.schools.school_repository import SchoolRepository
from app.infra.sqlite_types import coerce_int_columns


def _write_excel(df: pd.DataFrame, path: Path) -> None:
    df.to_excel(path, index=False)


def test_school_repository_imports_and_records_meta(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    repo = SchoolRepository(db)
    df = pd.DataFrame(
        {
            "کد مدرسه": [1, 2],
            "نام مدرسه": ["A", "B"],
            "مرکز گلستان صدرا": [10, 20],
            "جنسیت": [1, 2],
        }
    )
    path = tmp_path / "schools.xlsx"
    _write_excel(df, path)

    status = repo.import_from_excel(path, version_tag="v1")

    assert status.row_count == 2
    meta = db.fetch_reference_meta("schools")
    assert meta is not None
    _, source, row_count, version_tag, source_filename, imported_at = meta
    assert source == str(path)
    assert row_count == 2
    assert version_tag == "v1"
    assert source_filename == path.name
    assert imported_at is not None


def test_groupcode_repository_imports_and_records_meta(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    repo = GroupCodeRepository(db)
    df = pd.DataFrame(
        {
            "group_code": [11, 22],
            "level": ["L1", "L2"],
            "grade": [1, 2],
            "track": ["T1", "T2"],
        }
    )
    path = tmp_path / "groupcodes.xlsx"
    _write_excel(df, path)

    status = repo.import_from_excel(path, version_tag="gx")

    assert status.row_count == 2
    meta = db.fetch_reference_meta("groupcodes")
    assert meta is not None
    _, source, row_count, version_tag, source_filename, imported_at = meta
    assert source == str(path)
    assert row_count == 2
    assert version_tag == "gx"
    assert source_filename == path.name
    assert imported_at is not None


def test_missing_required_columns_raise(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    repo = SchoolRepository(db)
    df = pd.DataFrame({"کد مدرسه": [1]})
    path = tmp_path / "schools_bad.xlsx"
    _write_excel(df, path)

    with pytest.raises(DatabasePreparationError):
        repo.import_from_excel(path)


def test_school_parity_between_db_and_excel(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    repo = SchoolRepository(db)
    schools_df = pd.DataFrame(
        {
            "کد مدرسه": [1, 2],
            "نام مدرسه": ["A", "B"],
            "مرکز گلستان صدرا": [10, 20],
            "جنسیت": [1, 2],
            "فعال": [1, 0],
        }
    )
    path = tmp_path / "schools.xlsx"
    _write_excel(schools_df, path)

    repo.import_from_excel(path, version_tag="v_parity")

    excel_frame = canonicalize_headers(read_excel_first_sheet(path), header_mode="fa")
    excel_frame = coerce_int_columns(excel_frame, ["کد مدرسه", "مرکز گلستان صدرا", "جنسیت", "فعال"])
    excel_sorted = excel_frame.sort_values("کد مدرسه").reset_index(drop=True)

    db_frame = repo.load_canonical_frame().sort_values("کد مدرسه").reset_index(drop=True)

    pd.testing.assert_frame_equal(
        db_frame[excel_sorted.columns],
        excel_sorted,
        check_dtype=False,
        obj="schools parity",
    )


def test_groupcode_parity_between_db_and_excel(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    repo = GroupCodeRepository(db)
    groupcodes_df = pd.DataFrame(
        {
            "group_code": [11, 22],
            "level": ["L1", "L2"],
            "grade": [1, 2],
            "track": ["T1", "T2"],
            "is_active": [1, 1],
        }
    )
    path = tmp_path / "groupcodes.xlsx"
    _write_excel(groupcodes_df, path)

    repo.import_from_excel(path, version_tag="gc_parity")

    excel_frame = canonicalize_headers(read_excel_first_sheet(path), header_mode="en")
    excel_frame = coerce_int_columns(excel_frame, ["group_code", "grade", "is_active"])
    excel_sorted = excel_frame.sort_values("group_code").reset_index(drop=True)

    db_frame = repo.load_canonical_frame().sort_values("group_code").reset_index(drop=True)

    pd.testing.assert_frame_equal(
        db_frame[excel_sorted.columns],
        excel_sorted,
        check_dtype=False,
        obj="groupcodes parity",
    )


def test_parity_detects_missing_rows(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    repo = SchoolRepository(db)
    schools_df = pd.DataFrame(
        {
            "کد مدرسه": [1, 2, 3],
            "نام مدرسه": ["A", "B", "C"],
            "مرکز گلستان صدرا": [10, 20, 30],
            "جنسیت": [1, 2, 1],
            "فعال": [1, 1, 1],
        }
    )
    path = tmp_path / "schools.xlsx"
    _write_excel(schools_df, path)

    repo.import_from_excel(path)

    with db.connect() as conn:
        conn.execute('DELETE FROM schools WHERE "کد مدرسه" = 3')

    excel_frame = canonicalize_headers(read_excel_first_sheet(path), header_mode="fa")
    excel_frame = coerce_int_columns(excel_frame, ["کد مدرسه", "مرکز گلستان صدرا", "جنسیت", "فعال"])
    excel_sorted = excel_frame.sort_values("کد مدرسه").reset_index(drop=True)

    db_frame = repo.load_canonical_frame().sort_values("کد مدرسه").reset_index(drop=True)

    with pytest.raises(AssertionError):
        pd.testing.assert_frame_equal(
            db_frame[excel_sorted.columns],
            excel_sorted,
            check_dtype=False,
            obj="schools parity missing rows",
        )
