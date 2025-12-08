from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from app.infra.health import build_llm_debug_report, compute_run_health
from app.infra.local_database import LocalDatabase, RunRecord


def _sample_run_record(start: datetime) -> RunRecord:
    return RunRecord(
        run_uuid="run-test",
        started_at=start,
        finished_at=start,
        policy_version="1.0.3",
        ssot_version="1.0.2",
        entrypoint="allocate",
        cli_args=None,
        db_path=None,
        input_files_json="{}",
        input_hashes_json="{}",
        total_students=5,
        total_allocated=4,
        total_unallocated=1,
        history_metrics_json=None,
        qa_summary_json=None,
        status="success",
        message=None,
    )


def _setup_run_with_details(tmp_path, details: pd.DataFrame) -> tuple[LocalDatabase, int]:
    db = LocalDatabase(tmp_path / "health.db")
    db.initialize()
    now = datetime.now(UTC)
    run_id = db.insert_run(_sample_run_record(now))
    db.insert_qa_snapshot(run_id=run_id, qa_summary_df=None, qa_details_df=details)
    return db, run_id


def test_compute_run_health_status_ok(tmp_path) -> None:
    details = pd.DataFrame(
        [
            {"rule_id": "QA_RULE_SAMPLE", "level": "info", "student_id": 1},
        ]
    )
    db, run_id = _setup_run_with_details(tmp_path, details)
    summary = compute_run_health(str(run_id), db=db)
    assert summary.status == "OK"
    assert summary.counts["P2"] == 1


def test_compute_run_health_status_warn(tmp_path) -> None:
    details = pd.DataFrame(
        [
            {"rule_id": "QA_RULE_SAMPLE", "level": "warning", "student_id": 1},
            {"rule_id": "QA_RULE_SAMPLE", "level": "warning", "student_id": 2},
        ]
    )
    db, run_id = _setup_run_with_details(tmp_path, details)
    summary = compute_run_health(str(run_id), db=db)
    assert summary.status == "WARN"
    assert summary.counts["P1"] == 2


def test_compute_run_health_status_error(tmp_path) -> None:
    details = pd.DataFrame(
        [
            {"rule_id": "QA_RULE_SAMPLE", "level": "error", "student_id": 1},
        ]
    )
    db, run_id = _setup_run_with_details(tmp_path, details)
    summary = compute_run_health(str(run_id), db=db)
    assert summary.status == "ERROR"
    assert summary.counts["P0"] == 1


def test_build_llm_debug_report_limits_samples(tmp_path) -> None:
    details = pd.DataFrame(
        [{"rule_id": "QA_RULE_SAMPLE", "level": "error", "student_id": idx} for idx in range(5)]
    )
    db, run_id = _setup_run_with_details(tmp_path, details)
    report = build_llm_debug_report(str(run_id), db=db, sample_limit=3)
    assert set(report.keys()) >= {
        "meta",
        "health",
        "issues_summary",
        "samples",
        "allocation_snapshot",
    }
    assert report["samples"]
    first_sample = report["samples"][0]
    assert len(first_sample.get("rows", [])) == 3
