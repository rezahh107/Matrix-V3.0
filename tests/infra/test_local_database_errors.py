# file: tests/infra/test_local_database_errors.py
import sqlite3
from pathlib import Path

import pandas as pd
import pytest

from app.core.policy_loader import load_policy
from app.infra.errors import (
    DatabaseCorruptError,
    DatabaseOperationError,
    ReferenceDataMissingError,
    SchemaVersionMismatchError,
)
from app.infra.local_database import _SCHEMA_VERSION, LocalDatabase, RunMetricRow


def test_load_schools_missing_table(tmp_path):
    db = LocalDatabase(tmp_path / "missing.sqlite")
    with pytest.raises(ReferenceDataMissingError):
        db.load_schools()


def test_reference_crosswalk_missing(tmp_path):
    db = LocalDatabase(tmp_path / "crosswalk_missing.sqlite")
    with pytest.raises(ReferenceDataMissingError):
        db.load_school_crosswalk()


def test_database_operation_error_when_table_removed(tmp_path):
    db = LocalDatabase(tmp_path / "ops.sqlite")
    db.initialize()
    with db.connect() as conn:
        conn.execute("DROP TABLE run_metrics")
        conn.commit()
    metric_row = RunMetricRow(run_id=1, metric_key="demo", metric_value=1.0)
    with pytest.raises(DatabaseOperationError):
        db.insert_run_metrics([metric_row])


def test_schema_version_error_mapping(tmp_path):
    db = LocalDatabase(tmp_path / "schema_error.sqlite")
    db.initialize()
    with db.connect() as conn:
        conn.execute("UPDATE schema_meta SET schema_version = schema_version + 5 WHERE id = 1")
        conn.commit()
    with pytest.raises(SchemaVersionMismatchError):
        db.initialize()


def test_generic_sqlite_error_wrapped(tmp_path, monkeypatch):
    db = LocalDatabase(tmp_path / "generic.sqlite")
    db.initialize()
    df = pd.DataFrame({"کد مدرسه": [1], "نام مدرسه": ["الف"]})

    def boom(*_args, **_kwargs):
        raise sqlite3.OperationalError("failure")

    monkeypatch.setattr(db, "_replace_table_atomic", boom)
    with pytest.raises(DatabaseOperationError):
        db.upsert_schools(df)


def test_upsert_mentor_pool_cache_rejects_duplicate_composite_key(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "duplicate.sqlite")

    duplicated_pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m1"],
            "کد کارمندی پشتیبان": ["E1", "E1"],
            "کدرشته": [1201, 1201],
            "گروه آزمایشی": ["A", "A"],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 1],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3581],
        }
    )

    with pytest.raises(DatabaseOperationError) as excinfo:
        db.upsert_mentor_pool_cache(duplicated_pool, join_keys=policy.join_keys)

    message = str(excinfo.value)
    assert "mentor_pool_cache" in message
    assert "mentor_id" in message
    assert "کدرشته" in message
    assert "3581" in message


def test_upsert_mentor_pool_cache_allows_same_mentor_distinct_join_keys(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "duplicate_employee.sqlite")

    valid_pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m1"],
            "کد کارمندی پشتیبان": ["E1", "E1"],
            "کدرشته": [1201, 1202],
            "گروه آزمایشی": ["A", "B"],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 2],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3582],
        }
    )

    db.upsert_mentor_pool_cache(valid_pool, join_keys=policy.join_keys)


def test_upsert_students_cache_rejects_duplicate_student_ids(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "students_dup.sqlite")

    duplicated_students = pd.DataFrame(
        {
            "student_id": ["s1", "s1"],
            "کد ملی": ["1", "2"],
            "کدرشته": [1201, 1201],
            "گروه آزمایشی": ["A", "A"],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 1],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3581],
            "school_code_raw": ["x", "y"],
            "school_code_norm": [3581, 3581],
            "school_status_resolved": [1, 1],
        }
    )

    with pytest.raises(DatabaseOperationError) as excinfo:
        db.upsert_students_cache(duplicated_students, join_keys=policy.join_keys)

    message = str(excinfo.value)
    assert "students_cache" in message
    assert "student_id" in message
    assert "s1" in message


def test_upsert_caches_allow_nulls_in_unique_columns(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "nulls.sqlite")

    mentor_pool = pd.DataFrame(
        {
            "mentor_id": [None, None, "m2"],
            "کد کارمندی پشتیبان": [None, "E1", "E2"],
            "کدرشته": [1201, 1201, 1201],
            "جنسیت": [1, 1, 1],
            "دانش آموز فارغ": [0, 0, 0],
            "مرکز گلستان صدرا": [1, 1, 1],
            "مالی حکمت بنیاد": [0, 0, 0],
            "کد مدرسه": [3581, 3581, 3581],
            "remaining_capacity": [1.0, 1.0, 1.0],
            "allocations_new": [0, 0, 0],
            "occupancy_ratio": [0.0, 0.0, 0.0],
        }
    )

    students = pd.DataFrame(
        {
            "student_id": [None, None, "s3"],
            "کد ملی": ["1", "2", "3"],
            "کدرشته": [1201, 1201, 1201],
            "گروه آزمایشی": ["A", "A", "A"],
            "جنسیت": [1, 1, 1],
            "دانش آموز فارغ": [0, 0, 0],
            "مرکز گلستان صدرا": [1, 1, 1],
            "مالی حکمت بنیاد": [0, 0, 0],
            "کد مدرسه": [3581, 3581, 3581],
            "school_code_raw": ["x", "y", "z"],
            "school_code_norm": [3581, 3581, 3581],
            "school_status_resolved": [1, 1, 1],
        }
    )

    # نباید به‌خاطر NULL در ستون‌های کلید طبیعی خطا بدهد
    db.upsert_mentor_pool_cache(mentor_pool, join_keys=policy.join_keys)
    db.upsert_students_cache(students, join_keys=policy.join_keys)


def test_upsert_caches_create_unique_indexes(tmp_path: Path) -> None:
    policy = load_policy()
    db = LocalDatabase(tmp_path / "indexes.sqlite")

    mentor_pool = pd.DataFrame(
        {
            "mentor_id": ["m1", "m2"],
            "کد کارمندی پشتیبان": ["E1", "E2"],
            "کدرشته": [1201, 1202],
            "گروه آزمایشی": ["A", "B"],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 1],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3582],
            "remaining_capacity": [1.0, 1.0],
            "allocations_new": [0, 0],
            "occupancy_ratio": [0.0, 0.0],
        }
    )

    students = pd.DataFrame(
        {
            "student_id": ["s1", "s2"],
            "کد ملی": ["1", "2"],
            "کدرشته": [1201, 1202],
            "گروه آزمایشی": ["A", "B"],
            "جنسیت": [1, 1],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [1, 1],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [3581, 3582],
            "school_code_raw": ["x", "y"],
            "school_code_norm": [3581, 3582],
            "school_status_resolved": [1, 1],
        }
    )

    db.upsert_mentor_pool_cache(mentor_pool, join_keys=policy.join_keys)
    db.upsert_students_cache(students, join_keys=policy.join_keys)

    with db.connect() as conn:
        mentor_indexes = conn.execute("PRAGMA index_list('mentor_pool_cache')").fetchall()
        mentor_unique = {row[1] for row in mentor_indexes if row[2]}
        assert mentor_unique, "unique index for mentor pool should exist"

        composite_index_columns = {
            tuple(info[2] for info in conn.execute(f"PRAGMA index_info('{idx}')").fetchall())
            for idx in mentor_unique
        }
        assert (
            "mentor_id",
            "کدرشته",
            "جنسیت",
            "دانش آموز فارغ",
            "مرکز گلستان صدرا",
            "مالی حکمت بنیاد",
            "کد مدرسه",
        ) in composite_index_columns

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO mentor_pool_cache(
                    mentor_id,"کد کارمندی پشتیبان","کدرشته","گروه آزمایشی","جنسیت","دانش آموز فارغ","مرکز گلستان صدرا","مالی حکمت بنیاد","کد مدرسه"
                ) VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    "m1",
                    "E1",
                    1201,
                    "A",
                    1,
                    0,
                    1,
                    0,
                    3581,
                ),
            )

        student_indexes = conn.execute("PRAGMA index_list('students_cache')").fetchall()
        student_unique = {row[1] for row in student_indexes if row[2]}
        assert len(student_unique) >= 1

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO students_cache(student_id) VALUES (?)", ("s1",))


def test_initialize_reports_corrupt_file_with_backup(tmp_path):
    db_path = tmp_path / "corrupt.sqlite"
    db_path.write_text("not a sqlite database")
    db = LocalDatabase(db_path)

    with pytest.raises(DatabaseCorruptError):
        db.initialize()

    backup_path = db_path.with_suffix(db_path.suffix + ".corrupt")
    assert backup_path.exists()
    # اجرای مجدد باید بدون استثناء و با نسخهٔ صحیح انجام شود
    db.initialize()
    with db.connect() as conn:
        version = conn.execute("SELECT schema_version FROM schema_meta WHERE id = 1").fetchone()[0]
    assert version == _SCHEMA_VERSION


def test_initialize_repairs_missing_mentor_group_column(tmp_path: Path) -> None:
    db_path = tmp_path / "missing_group.sqlite"
    db = LocalDatabase(db_path)

    with db.connect() as conn:
        LocalDatabase._ensure_schema_meta_table(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO schema_meta(
                id, schema_version, policy_version, ssot_version, created_at
            )
            VALUES (1, ?, '1.0.3', '1.0.2', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            """,
            (_SCHEMA_VERSION,),
        )
        conn.execute(
            """
            CREATE TABLE mentor_pool_cache (
                mentor_id TEXT,
                "کد کارمندی پشتیبان" TEXT,
                "کدرشته" INTEGER,
                "جنسیت" INTEGER,
                "دانش آموز فارغ" INTEGER,
                "مرکز گلستان صدرا" INTEGER,
                "مالی حکمت بنیاد" INTEGER,
                "کد مدرسه" INTEGER,
                remaining_capacity REAL,
                allocations_new INTEGER,
                occupancy_ratio REAL
            )
            """,
        )
        conn.commit()

    db.initialize()

    with db.connect() as conn:
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(mentor_pool_cache)").fetchall()
        }

    assert "گروه آزمایشی" in columns


def test_initialize_repairs_schema_when_students_cache_missing_student_id(tmp_path):
    db_path = tmp_path / "missing_column.sqlite"
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
            " VALUES (1, ?, '1.0.0', '1.0.0', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))",
            (_SCHEMA_VERSION,),
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
        columns = {row[1] for row in conn.execute("PRAGMA table_info('students_cache')")}

    assert "student_id" in columns


def test_initialize_creates_students_cache_with_student_id_column(tmp_path):
    db = LocalDatabase(tmp_path / "fresh.sqlite")
    db.initialize()

    with db.connect() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info('students_cache')")}
    assert "student_id" in cols


def test_get_schema_diagnostics_reports_missing_student_id(tmp_path):
    db_path = tmp_path / "broken.sqlite"
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
            " VALUES (1, ?, '1.0.0', '1.0.0', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))",
            (_SCHEMA_VERSION,),
        )
        conn.execute(
            """
            CREATE TABLE students_cache (
                "کد ملی" TEXT,
                "کدرشته" INTEGER
            )
            """
        )
        conn.commit()

    db = LocalDatabase(db_path)
    diagnostics = db.get_schema_diagnostics()
    target = next(diag for diag in diagnostics.tables if diag.name == "students_cache")
    assert "student_id" in target.missing_required_columns
