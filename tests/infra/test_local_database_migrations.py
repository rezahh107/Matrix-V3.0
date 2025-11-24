from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Iterable

from app.infra.local_database import LocalDatabase, _SCHEMA_VERSION


def _list_user_tables(conn: sqlite3.Connection) -> set[str]:
    """استخراج فهرست جدول‌های کاربری بدون جدول‌های داخلی SQLite."""

    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def _bootstrap_legacy_db(path: Path, version: int, *, tables: Iterable[str] = ()) -> None:
    """ساخت پایگاه‌دادهٔ آزمایشی با نسخهٔ قدیمی schema_meta و چند جدول ساده."""

    with sqlite3.connect(path) as conn:
        LocalDatabase._ensure_schema_meta_table(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO schema_meta(id, schema_version, policy_version, ssot_version, created_at)
            VALUES (1, ?, '1.0.3', '1.0.2', ?)
            """,
            (version, datetime.utcnow().isoformat() + "Z"),
        )
        for table in tables:
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} (id INTEGER PRIMARY KEY AUTOINCREMENT)")
        conn.commit()


def test_initialize_migrates_all_supported_versions(tmp_path: Path) -> None:
    canonical = LocalDatabase(tmp_path / "canonical.sqlite")
    canonical.initialize()
    with canonical.connect() as conn:
        expected_tables = _list_user_tables(conn)

    legacy_versions = (2, 3, 5)
    for legacy_version in legacy_versions:
        legacy_path = tmp_path / f"legacy_v{legacy_version}.sqlite"
        _bootstrap_legacy_db(legacy_path, legacy_version, tables=("runs",))
        db = LocalDatabase(legacy_path)
        db.initialize()

        with db.connect() as conn:
            version = conn.execute(
                "SELECT schema_version FROM schema_meta WHERE id = 1"
            ).fetchone()[0]
            migrated_tables = _list_user_tables(conn)

        assert int(version) == _SCHEMA_VERSION
        assert migrated_tables == expected_tables


def test_initialize_sets_expected_tables_for_new_database(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "fresh.sqlite")
    db.initialize()

    with db.connect() as conn:
        migrated_tables = _list_user_tables(conn)
        version = conn.execute("SELECT schema_version FROM schema_meta WHERE id = 1").fetchone()[0]

    assert int(version) == _SCHEMA_VERSION
    assert "runs" in migrated_tables
    assert "forms_entries" in migrated_tables
    assert "qa_summary" in migrated_tables
    assert "trace_snapshots" in migrated_tables


def test_initialize_adds_student_id_column_when_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "missing_student_id.sqlite"

    with sqlite3.connect(db_path) as conn:
        LocalDatabase._ensure_schema_meta_table(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO schema_meta(id, schema_version, policy_version, ssot_version, created_at)
            VALUES (1, 9, '1.0.3', '1.0.2', ?)
            """,
            (datetime.utcnow().isoformat() + "Z",),
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
                "کد مدرسه" INTEGER,
                school_code_raw TEXT,
                school_code_norm INTEGER,
                school_status_resolved INTEGER
            )
            """
        )
        conn.commit()

    db = LocalDatabase(db_path)
    db.initialize()

    with db.connect() as conn:
        version = conn.execute(
            "SELECT schema_version FROM schema_meta WHERE id = 1"
        ).fetchone()[0]
        columns = {row[1] for row in conn.execute("PRAGMA table_info('students_cache')")}

    assert int(version) == _SCHEMA_VERSION
    assert "student_id" in columns

def test_initialize_is_idempotent_when_student_id_already_exists(tmp_path: Path) -> None:
    canonical_path = tmp_path / "canonical.sqlite"
    canonical = LocalDatabase(canonical_path)
    canonical.initialize()

    with canonical.connect() as conn:
        canonical_columns = {
            row[1] for row in conn.execute("PRAGMA table_info('students_cache')")
        }

    db_path = tmp_path / "already_migrated.sqlite"
    with sqlite3.connect(canonical_path) as src, sqlite3.connect(db_path) as dst:
        src.backup(dst)
    db = LocalDatabase(db_path)

    db.initialize()
    db.initialize()

    with db.connect() as conn:
        version = conn.execute(
            "SELECT schema_version FROM schema_meta WHERE id = 1"
        ).fetchone()[0]
        columns = {row[1] for row in conn.execute("PRAGMA table_info('students_cache')")}

    assert int(version) == _SCHEMA_VERSION
    assert columns == canonical_columns


def test_migrate_from_v8_to_v10_when_students_cache_is_missing(tmp_path: Path) -> None:
    canonical_path = tmp_path / "canonical.sqlite"
    canonical = LocalDatabase(canonical_path)
    canonical.initialize()

    with canonical.connect() as conn:
        expected_student_columns = {
            row[1] for row in conn.execute("PRAGMA table_info('students_cache')")
        }
        expected_qa_columns = {
            row[1] for row in conn.execute("PRAGMA table_info('qa_snapshots')")
        }

    legacy_path = tmp_path / "legacy_v8.sqlite"
    _bootstrap_legacy_db(legacy_path, 8)

    db = LocalDatabase(legacy_path)
    db.initialize()

    with db.connect() as conn:
        version = conn.execute(
            "SELECT schema_version FROM schema_meta WHERE id = 1"
        ).fetchone()[0]
        student_columns = {
            row[1] for row in conn.execute("PRAGMA table_info('students_cache')")
        }
        qa_columns = {
            row[1] for row in conn.execute("PRAGMA table_info('qa_snapshots')")
        }

    assert int(version) == _SCHEMA_VERSION
    assert student_columns == expected_student_columns
    assert qa_columns == expected_qa_columns


def test_migrate_v8_to_v10_and_reinitialize_is_idempotent(tmp_path: Path) -> None:
    canonical_path = tmp_path / "canonical.sqlite"
    canonical = LocalDatabase(canonical_path)
    canonical.initialize()

    db_path = tmp_path / "prepopulated_v8.sqlite"
    with sqlite3.connect(canonical_path) as src, sqlite3.connect(db_path) as dst:
        src.backup(dst)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE schema_meta SET schema_version = 8 WHERE id = 1"
        )
        conn.commit()

    db = LocalDatabase(db_path)
    db.initialize()
    db.initialize()

    with db.connect() as conn:
        version = conn.execute(
            "SELECT schema_version FROM schema_meta WHERE id = 1"
        ).fetchone()[0]
        student_columns = {
            row[1] for row in conn.execute("PRAGMA table_info('students_cache')")
        }
        qa_columns = {
            row[1] for row in conn.execute("PRAGMA table_info('qa_snapshots')")
        }

    with canonical.connect() as conn:
        expected_student_columns = {
            row[1] for row in conn.execute("PRAGMA table_info('students_cache')")
        }
        expected_qa_columns = {
            row[1] for row in conn.execute("PRAGMA table_info('qa_snapshots')")
        }

    assert int(version) == _SCHEMA_VERSION
    assert student_columns == expected_student_columns
    assert qa_columns == expected_qa_columns
