from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.infra.local_database import LocalDatabase, RunMetricRow, RunRecord


def _build_run_record(run_uuid: str) -> RunRecord:
    timestamp = pd.Timestamp("2024-01-01T00:00:00Z").to_pydatetime()
    return RunRecord(
        run_uuid=run_uuid,
        started_at=timestamp,
        finished_at=timestamp,
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


def test_fetch_metrics_for_runs_chunks_over_sqlite_limit(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "bulk.sqlite")
    db.initialize()

    run1 = db.insert_run(_build_run_record("run-1"))
    run2 = db.insert_run(_build_run_record("run-2"))
    db.insert_run_metrics(
        [
            RunMetricRow(run_id=run1, metric_key="SCHOOL.students_total", metric_value=2.0),
            RunMetricRow(run_id=run1, metric_key="SCHOOL.students_allocated", metric_value=1.0),
            RunMetricRow(run_id=run2, metric_key="NORMAL.students_total", metric_value=3.0),
        ]
    )

    run_ids = list(range(1, 1201))
    metrics = db.fetch_metrics_for_runs(run_ids)

    assert run1 in metrics
    assert run2 in metrics
    assert metrics[500] == []

    run1_keys = [row["metric_key"] for row in metrics[run1]]
    assert run1_keys == ["SCHOOL.students_total", "SCHOOL.students_allocated"]
