import sqlite3

import pytest

from app.infra import cli
from app.infra.errors import (
    DatabaseCorruptError,
    DatabaseSchemaMismatchError,
    SchemaVersionMismatchError,
)
from app.infra.local_database import LocalDatabase


def _capture_progress() -> tuple[list[str], cli.ProgressFn]:
    messages: list[str] = []

    def _progress(_pct: int, msg: str) -> None:
        messages.append(msg)

    return messages, _progress


def test_prepare_db_success_first_run(tmp_path):
    db = LocalDatabase(tmp_path / "first.sqlite")
    messages, progress = _capture_progress()

    cli._prepare_local_db(db, progress)

    assert db.path.exists()
    assert messages == []


def test_prepare_db_schema_too_old_reports_hint(tmp_path):
    db = LocalDatabase(tmp_path / "old.sqlite")
    with db.connect() as conn:
        conn.execute(
            """
            CREATE TABLE schema_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                schema_version INTEGER NOT NULL,
                policy_version TEXT,
                ssot_version TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_meta (id, schema_version, policy_version, ssot_version, created_at)"
            " VALUES (1, 1, '1.0.0', '1.0.0', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"
        )
        conn.commit()

    messages, progress = _capture_progress()
    with pytest.raises(SchemaVersionMismatchError):
        cli._prepare_local_db(db, progress)

    assert any("خطا در آماده‌سازی پایگاه داده" in msg for msg in messages)
    assert any("حذف" in msg or "بازسازی" in msg for msg in messages)


def test_prepare_db_corrupt_file_includes_backup_hint(tmp_path):
    db_path = tmp_path / "corrupt.sqlite"
    db_path.write_text("broken")
    db = LocalDatabase(db_path)
    messages, progress = _capture_progress()

    with pytest.raises(DatabaseCorruptError):
        cli._prepare_local_db(db, progress)

    backup_path = db_path.with_suffix(db_path.suffix + ".corrupt")
    assert backup_path.exists()
    assert any("خراب" in msg for msg in messages)
    assert any("بکاپ" in msg for msg in messages)


def test_prepare_db_schema_mismatch_missing_column(tmp_path):
    db_path = tmp_path / "missing_col.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE schema_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                schema_version INTEGER NOT NULL,
                policy_version TEXT NOT NULL,
                ssot_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_meta (id, schema_version, policy_version, ssot_version, created_at)"
            " VALUES (1, 8, '1.0.0', '1.0.0', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"
        )
        conn.execute(
            """
            CREATE TABLE students_cache (
                "کد ملی" TEXT,
                "کدرشته" INTEGER,
                "گروه آزمایشی" TEXT,
                "جنسیت" INTEGER,
                "دانش آموز فارغ" INTEGER,
                "مرکز گلستان صدرا" INTEGER,
                "مالی حکمت بنیاد" INTEGER,
                "کد مدرسه" INTEGER
            )
            """
        )
        conn.commit()

    db = LocalDatabase(db_path)
    messages, progress = _capture_progress()

    with pytest.raises(DatabaseSchemaMismatchError):
        cli._prepare_local_db(db, progress)

    assert any("ساختار" in msg or "سازگار" in msg for msg in messages)
    assert any("حذف" in msg or "بازسازی" in msg for msg in messages)
    assert not any("دسترسی" in msg and "دیسک" in msg for msg in messages)
