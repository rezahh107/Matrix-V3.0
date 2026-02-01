from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.infra.errors import DatabasePreparationError
from app.infra.local_database import LocalDatabase
from app.infra.references.schools import import_school_report_from_excel


def _write_school_report(path: Path, *, include_gender: bool = True) -> None:
    data: dict[str, list[object]] = {
        "کد مدرسه": [101, 102],
        "نام مدرسه": ["الف", "ب"],
    }
    if include_gender:
        data["جنسیت"] = [1, 0]
    frame = pd.DataFrame(data)
    frame.to_excel(path, index=False)


def test_schoolreport_strict_missing_required_raises(tmp_path: Path) -> None:
    report_path = tmp_path / "SchoolReport.xlsx"
    frame = pd.DataFrame(
        {
            "کد مدرسه": [101, 102],
            "جنسیت": [1, 0],
        }
    )
    frame.to_excel(report_path, index=False)
    db = LocalDatabase(tmp_path / "schools.db")
    db.initialize()
    with pytest.raises(DatabasePreparationError) as excinfo:
        import_school_report_from_excel(report_path, db=db, compat_mode=False)
    assert "نام مدرسه" in (excinfo.value.hint or "")


def test_schoolreport_strict_accepts_minimal_columns(tmp_path: Path) -> None:
    report_path = tmp_path / "SchoolReport.xlsx"
    _write_school_report(report_path, include_gender=False)
    db = LocalDatabase(tmp_path / "schools.db")
    db.initialize()
    normalized = import_school_report_from_excel(report_path, db=db, compat_mode=False)
    assert "مرکز گلستان صدرا" not in normalized.columns
    assert "جنسیت" not in normalized.columns
    assert normalized.attrs.get("compat_notes") is None


def test_schoolreport_compat_handles_wide_center_columns(tmp_path: Path) -> None:
    report_path = tmp_path / "SchoolReport.xlsx"
    frame = pd.DataFrame(
        {
            "کد مدرسه": [101, 102],
            "نام مدرسه": ["الف", "ب"],
            "جنسیت": [1, 0],
            "مرکز 12": [1, 1],
        }
    )
    frame.to_excel(report_path, index=False)
    db = LocalDatabase(tmp_path / "schools.db")
    db.initialize()
    normalized = import_school_report_from_excel(report_path, db=db, compat_mode=True)
    compat_warnings = normalized.attrs.get("compat_warnings")
    assert compat_warnings
    assert compat_warnings[0]["issue"] == "WIDE_CENTER_COLUMN"


def test_schoolreport_accepts_gender_tokens_and_keeps_namayandegi(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "SchoolReport.xlsx"
    frame = pd.DataFrame(
        {
            "کد مدرسه": [201, 202],
            "نام مدرسه": ["دبیرستان الف", "دبیرستان ب"],
            "جنسیت": ["پسرانه", "دخترانه"],
            "نمایندگی": [3570, 3730],
        }
    )
    frame.to_excel(report_path, index=False)
    db = LocalDatabase(tmp_path / "schools.db")
    db.initialize()
    normalized = import_school_report_from_excel(report_path, db=db, compat_mode=False)
    assert "نمایندگی" in normalized.columns
    assert normalized["جنسیت"].astype(int).tolist() == [1, 0]
    loaded = db.load_schools()
    assert not loaded.empty
