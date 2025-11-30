from datetime import datetime
from pathlib import Path

from app.infra.local_database import _POLICY_VERSION, _SCHEMA_VERSION, _SSOT_VERSION, LocalDatabase


def _insert_dummy_run(db: LocalDatabase) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                run_uuid, started_at, finished_at, policy_version, ssot_version,
                entrypoint, cli_args, db_path, input_files_json, input_hashes_json,
                total_students, total_allocated, total_unallocated,
                history_metrics_json, qa_summary_json, status, message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "uuid-1",
                datetime.utcnow().isoformat(),
                datetime.utcnow().isoformat(),
                "1.0.3",
                "1.0.2",
                "test",
                None,
                str(db.path),
                "{}",
                "{}",
                1,
                1,
                0,
                None,
                None,
                "ok",
                None,
            ),
        )
        conn.commit()


def _insert_cache_rows(db: LocalDatabase) -> None:
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO students_cache (
                student_id, "کد ملی", "کدرشته", "گروه آزمایشی", "جنسیت", "دانش آموز فارغ",
                "مرکز گلستان صدرا", "مالی حکمت بنیاد", "کد مدرسه", school_code_raw,
                school_code_norm, school_status_resolved
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "s1",
                "001",
                101,
                "گروه",
                1,
                0,
                10,
                1,
                1000,
                None,
                None,
                None,
            ),
        )
        conn.execute(
            """
            INSERT INTO mentor_pool_cache (
                mentor_id, "کد کارمندی پشتیبان", "کدرشته", "گروه آزمایشی", "جنسیت",
                "دانش آموز فارغ", "مرکز گلستان صدرا", "مالی حکمت بنیاد", "کد مدرسه",
                remaining_capacity, allocations_new, occupancy_ratio, policy_version, ssot_version, pool_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "m1",
                "emp1",
                101,
                "گروه",
                1,
                0,
                10,
                1,
                1000,
                5.0,
                0,
                0.0,
                _POLICY_VERSION,
                _SSOT_VERSION,
                "",
            ),
        )
        conn.execute(
            'INSERT INTO managers_reference ("نام مدیر", "مرکز گلستان صدرا") VALUES (?, ?)',
            ("مدیر", 10),
        )
        conn.execute(
            "INSERT INTO forms_entries (entry_id, form_id, received_at, normalized_at) VALUES (?, ?, ?, ?)",
            ("e1", "f1", datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
        )
        conn.commit()


def test_reset_full_database_creates_backup_and_fresh_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "smart_alloc.db"
    db = LocalDatabase(db_path)
    db.initialize()
    _insert_cache_rows(db)

    backup = db.reset_full_database()

    assert backup is not None
    assert backup.exists()
    assert db_path.exists()
    assert db.get_schema_version() == _SCHEMA_VERSION
    # ستون student_id باید در Schema تازه وجود داشته باشد
    with db.connect() as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(students_cache)")}
    assert "student_id" in columns


def test_clear_caches_truncates_cache_tables_but_preserves_history(tmp_path: Path) -> None:
    db_path = tmp_path / "smart_alloc.db"
    db = LocalDatabase(db_path)
    db.initialize()
    _insert_cache_rows(db)
    _insert_dummy_run(db)

    db.clear_caches()

    with db.connect() as conn:
        cache_counts = {
            "students_cache": conn.execute("SELECT COUNT(*) FROM students_cache").fetchone()[0],
            "mentor_pool_cache": conn.execute("SELECT COUNT(*) FROM mentor_pool_cache").fetchone()[
                0
            ],
            "managers_reference": conn.execute(
                "SELECT COUNT(*) FROM managers_reference"
            ).fetchone()[0],
            "forms_entries": conn.execute("SELECT COUNT(*) FROM forms_entries").fetchone()[0],
        }
        runs_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
    assert all(count == 0 for count in cache_counts.values())
    assert runs_count == 1
