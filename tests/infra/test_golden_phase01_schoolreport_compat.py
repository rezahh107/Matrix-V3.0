from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.infra.errors import DatabasePreparationError
from app.infra.local_database import LocalDatabase
from app.infra.references.schools import import_school_report_from_excel


def _write_school_report(path: Path) -> None:
    frame = pd.DataFrame(
        {
            "کد مدرسه": [101, 102],
            "نام مدرسه": ["الف", "ب"],
            "جنسیت": [1, 0],
        }
    )
    frame.to_excel(path, index=False)


def test_schoolreport_strict_missing_required_raises(tmp_path: Path) -> None:
    report_path = tmp_path / "SchoolReport.xlsx"
    _write_school_report(report_path)
    db = LocalDatabase(tmp_path / "schools.db")
    db.initialize()
    with pytest.raises(DatabasePreparationError):
        import_school_report_from_excel(report_path, db=db, compat_mode=False)


def test_schoolreport_compat_applies_defaults(tmp_path: Path) -> None:
    report_path = tmp_path / "SchoolReport.xlsx"
    _write_school_report(report_path)
    db = LocalDatabase(tmp_path / "schools.db")
    db.initialize()
    normalized = import_school_report_from_excel(report_path, db=db, compat_mode=True)
    assert "مرکز گلستان صدرا" in normalized.columns
    assert normalized["مرکز گلستان صدرا"].fillna(0).astype(int).eq(0).all()
    compat_notes = normalized.attrs.get("compat_notes")
    assert compat_notes


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
    assert "مرکز گلستان صدرا" in normalized.columns
    compat_warnings = normalized.attrs.get("compat_warnings")
    assert compat_warnings
    assert compat_warnings[0]["issue"] == "WIDE_CENTER_COLUMN"
