import sqlite3
from pathlib import Path

from app.infra.local_database import LocalDatabase


def test_initialize_creates_run_metrics_indexes(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "indexes.sqlite")
    db.initialize()

    with db.connect() as conn:
        run_metrics_indexes = {
            row[1] for row in conn.execute("PRAGMA index_list('run_metrics')").fetchall()
        }
        qa_summary_indexes = {
            row[1] for row in conn.execute("PRAGMA index_list('qa_summary')").fetchall()
        }

    assert "idx_run_metrics_run_id" in run_metrics_indexes
    assert "idx_qa_summary_run_id" in qa_summary_indexes


def test_migrate_v12_adds_run_metrics_indexes(tmp_path: Path) -> None:
    db_path = tmp_path / "schema_v12.sqlite"
    db = LocalDatabase(db_path)

    with sqlite3.connect(db_path) as conn:
        LocalDatabase._ensure_schema_meta_table(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO schema_meta(id, schema_version, policy_version, ssot_version, created_at)
            VALUES (1, 12, '1.0.3', '1.0.2', '2024-01-01T00:00:00Z')
            """
        )
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_uuid TEXT NOT NULL UNIQUE,
                started_at TEXT NOT NULL,
                finished_at TEXT NOT NULL,
                policy_version TEXT NOT NULL,
                ssot_version TEXT NOT NULL,
                entrypoint TEXT NOT NULL,
                cli_args TEXT,
                db_path TEXT,
                input_files_json TEXT,
                input_hashes_json TEXT,
                total_students INTEGER,
                total_allocated INTEGER,
                total_unallocated INTEGER,
                history_metrics_json TEXT,
                qa_summary_json TEXT,
                status TEXT NOT NULL,
                message TEXT
            );
            CREATE TABLE IF NOT EXISTS run_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                metric_key TEXT NOT NULL,
                metric_value REAL NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS qa_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                violation_code TEXT NOT NULL,
                severity TEXT NOT NULL,
                count INTEGER NOT NULL,
                FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()

    db.initialize()

    with db.connect() as conn:
        run_metrics_indexes = {
            row[1] for row in conn.execute("PRAGMA index_list('run_metrics')").fetchall()
        }
        qa_summary_indexes = {
            row[1] for row in conn.execute("PRAGMA index_list('qa_summary')").fetchall()
        }

    assert "idx_run_metrics_run_id" in run_metrics_indexes
    assert "idx_qa_summary_run_id" in qa_summary_indexes
