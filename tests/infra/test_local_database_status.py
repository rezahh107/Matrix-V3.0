import sqlite3
from datetime import datetime

from app.infra.local_database import (
    DatabaseHealthReason,
    DatabaseHealthStatus,
    LocalDatabase,
    RunRecord,
)


def test_health_unavailable_when_missing(tmp_path):
    db = LocalDatabase(tmp_path / "missing.sqlite")

    summary = db.get_database_health_summary()

    assert summary.status is DatabaseHealthStatus.UNAVAILABLE
    assert "در دسترس نیست" in summary.message
    assert summary.reason is DatabaseHealthReason.MISSING_FILE
    assert summary.counts == {}


def test_health_degraded_when_tables_missing(tmp_path):
    db_path = tmp_path / "degraded.sqlite"
    sqlite3.connect(db_path).close()
    db = LocalDatabase(db_path)

    summary = db.get_database_health_summary()

    assert summary.status is DatabaseHealthStatus.DEGRADED
    assert summary.reason is DatabaseHealthReason.NEEDS_REVIEW
    assert summary.counts.get("دانش‌آموز") == 0


def test_health_ok_with_empty_schema(tmp_path):
    db = LocalDatabase(tmp_path / "empty.sqlite")
    db.initialize()

    summary = db.get_database_health_summary()

    assert summary.status is DatabaseHealthStatus.OK
    assert summary.reason is DatabaseHealthReason.READY
    assert summary.counts == {"دانش‌آموز": 0, "پشتیبان": 0, "اجرا": 0}
    assert summary.last_updated is not None


def test_health_counts_with_data(tmp_path):
    db = LocalDatabase(tmp_path / "data.sqlite")
    db.initialize()
    with db.connect() as conn:
        conn.execute("INSERT INTO students_cache (student_id) VALUES (?)", ("s1",))
        conn.execute(
            "INSERT INTO mentor_pool_cache (mentor_id, policy_version, ssot_version, pool_hash)"
            " VALUES (?, ?, ?, ?)",
            ("m1", "1.0.3", "1.0.2", ""),
        )
    record = RunRecord(
        run_uuid="run-1",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        policy_version="1.0.3",
        ssot_version="1.0.2",
        entrypoint="ui",
        cli_args=None,
        db_path=None,
        input_files_json="[]",
        input_hashes_json="{}",
        total_students=1,
        total_allocated=1,
        total_unallocated=0,
        history_metrics_json=None,
        qa_summary_json=None,
        status="success",
        message=None,
    )
    db.insert_run(record)

    summary = db.get_database_health_summary()

    assert summary.status is DatabaseHealthStatus.OK
    assert summary.counts["دانش‌آموز"] == 1
    assert summary.counts["پشتیبان"] == 1
    assert summary.counts["اجرا"] == 1
    assert summary.last_updated is not None


def test_health_connection_error_has_distinct_reason(tmp_path):
    # Real SQLite error after file existence check (not a missing path).
    path = tmp_path / "invalid.sqlite"
    path.write_bytes(b"not an SQLite database")
    summary = LocalDatabase(path).get_database_health_summary()

    assert summary.status is DatabaseHealthStatus.UNAVAILABLE
    assert summary.reason is DatabaseHealthReason.CONNECTION_ERROR
    assert "خطای اتصال" in summary.message
    assert summary.counts == {}
