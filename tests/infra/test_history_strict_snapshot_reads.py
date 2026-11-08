"""Strict history-audit reads surface corruption without migrating legacy readers."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.infra.errors import DatabaseOperationError
from app.infra.local_database import LocalDatabase, RunRecord


def _db_with_history(path: Path) -> tuple[LocalDatabase, int]:
    db = LocalDatabase(path)
    db.initialize()
    now = datetime(2026, 11, 8, tzinfo=UTC)
    run_id = db.insert_run(
        RunRecord(
            run_uuid="synthetic-run",
            started_at=now,
            finished_at=now,
            policy_version="1.0.3",
            ssot_version="1.0.2",
            entrypoint="allocate",
            cli_args=None,
            db_path=None,
            input_files_json="{}",
            input_hashes_json="{}",
            total_students=1,
            total_allocated=1,
            total_unallocated=0,
            history_metrics_json=None,
            qa_summary_json=None,
            status="success",
            message=None,
        )
    )
    db.insert_trace_snapshot(
        run_id=run_id, trace_df=pd.DataFrame({"student_id": ["synthetic-student"]})
    )
    db.insert_qa_snapshot(
        run_id=run_id,
        qa_summary_df=pd.DataFrame({"rule_id": ["QA-OK"]}),
        qa_details_df=pd.DataFrame({"student_id": ["synthetic-student"]}),
        qa_extras={"allocations": pd.DataFrame({"student_id": ["synthetic-student"]})},
    )
    return db, run_id


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("trace_snapshots", "trace_json"),
        ("qa_snapshots", "qa_summary_json"),
        ("qa_snapshots", "qa_extras_json"),
    ],
)
def test_corrupt_snapshot_requires_strict_failure_without_changing_record(
    tmp_path: Path, table: str, column: str
) -> None:
    db, run_id = _db_with_history(tmp_path / "history.sqlite")
    with sqlite3.connect(db.path) as conn:
        conn.execute(
            f"UPDATE {table} SET {column} = ? WHERE run_id = ?",
            ("{invalid-synthetic-json", run_id),
        )
        conn.commit()
    reader = db.fetch_trace_snapshot if table == "trace_snapshots" else db.fetch_qa_snapshot
    with pytest.raises(DatabaseOperationError, match="Invalid stored snapshot"):
        reader(run_id, strict=True)
    # Existing readers remain compatible: invalid snapshot was historically absent.
    without_strict = reader(run_id)
    if table == "trace_snapshots" or column == "qa_summary_json":
        assert without_strict[0] is None
    else:
        assert without_strict[2] == {}
    with sqlite3.connect(db.path) as conn:
        saved = conn.execute(
            f"SELECT {column} FROM {table} WHERE run_id = ?", (run_id,)
        ).fetchone()
    assert saved == ("{invalid-synthetic-json",)
    assert db.fetch_run_by_id(run_id)["run_uuid"] == "synthetic-run"


def test_strict_qa_extras_rejects_corrupt_nested_frame(tmp_path: Path) -> None:
    db, run_id = _db_with_history(tmp_path / "history.sqlite")
    payload = json.dumps({"allocations": "{invalid-nested-json"})
    with sqlite3.connect(db.path) as conn:
        conn.execute(
            "UPDATE qa_snapshots SET qa_extras_json = ? WHERE run_id = ?", (payload, run_id)
        )
        conn.commit()
    with pytest.raises(DatabaseOperationError, match="Invalid stored snapshot"):
        db.fetch_qa_snapshot(run_id, strict=True)
    assert db.fetch_qa_snapshot(run_id)[2] == {}


def test_valid_or_missing_strict_snapshots_preserve_existing_semantics(tmp_path: Path) -> None:
    db, run_id = _db_with_history(tmp_path / "history.sqlite")
    trace, _, _ = db.fetch_trace_snapshot(run_id, strict=True)
    qa, details, extras = db.fetch_qa_snapshot(run_id, strict=True)
    assert trace is not None and trace.loc[0, "student_id"] == "synthetic-student"
    assert qa is not None and qa.loc[0, "rule_id"] == "QA-OK"
    assert details is not None and details.loc[0, "student_id"] == "synthetic-student"
    assert extras["allocations"].loc[0, "student_id"] == "synthetic-student"
    assert db.fetch_trace_snapshot(run_id + 10, strict=True) == (None, None, None)
    assert db.fetch_qa_snapshot(run_id + 10, strict=True) == (None, None, {})


@pytest.mark.parametrize(
    "nested_payload", [None, ""], ids=["explicit-null", "explicit-empty-string"]
)
def test_strict_qa_extras_rejects_explicitly_present_absent_nested_frame(
    tmp_path: Path, nested_payload: str | None
) -> None:
    db, run_id = _db_with_history(tmp_path / "history.sqlite")
    payload = json.dumps({"allocations": nested_payload})
    with sqlite3.connect(db.path) as conn:
        conn.execute(
            "UPDATE qa_snapshots SET qa_extras_json = ? WHERE run_id = ?",
            (payload, run_id),
        )
        conn.commit()

    # An entry explicitly included in the map is never an absent optional snapshot.
    with pytest.raises(
        DatabaseOperationError, match=r"Invalid stored snapshot: qa_extras\.allocations"
    ):
        db.fetch_qa_snapshot(run_id, strict=True)

    # Historical lenient readers retain the original skip semantics.
    assert db.fetch_qa_snapshot(run_id)[2] == {}
    with sqlite3.connect(db.path) as conn:
        saved = conn.execute(
            "SELECT qa_extras_json FROM qa_snapshots WHERE run_id = ?", (run_id,)
        ).fetchone()
    assert saved == (payload,)
    db.close_all_connections()


def test_strict_qa_extras_distinguishes_valid_empty_map_from_absent_optional_value(
    tmp_path: Path,
) -> None:
    db, run_id = _db_with_history(tmp_path / "history.sqlite")
    for payload in (None, "", "{}"):
        with sqlite3.connect(db.path) as conn:
            conn.execute(
                "UPDATE qa_snapshots SET qa_extras_json = ? WHERE run_id = ?",
                (payload, run_id),
            )
            conn.commit()
        summary, details, extras = db.fetch_qa_snapshot(run_id, strict=True)
        assert summary is not None and summary.at[0, "rule_id"] == "QA-OK"
        assert details is not None and details.at[0, "student_id"] == "synthetic-student"
        assert extras == {}
        assert db.fetch_qa_snapshot(run_id)[2] == {}
    db.close_all_connections()
