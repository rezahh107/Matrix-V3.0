"""P0 regression: an issue-free or missing snapshot is not proof of QA PASS."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from app.infra.health import build_llm_debug_report, compute_run_health
from app.infra.local_database import LocalDatabase, QaSummaryRow, RunRecord


@pytest.fixture
def db(tmp_path):
    database = LocalDatabase(tmp_path / "synthetic-qa-truthfulness.db")
    database.initialize()
    try:
        yield database
    finally:
        database.close_all_connections()


def _run(
    db: LocalDatabase, *,
    outcome: dict | str | None = None,
    status: str = "success",
    token: str = "run",
) -> int:
    now = datetime.now(UTC)
    serialized = json.dumps(outcome) if isinstance(outcome, dict) else outcome
    return db.insert_run(
        RunRecord(
            run_uuid=token,
            started_at=now, finished_at=now,
            policy_version="synthetic", ssot_version="synthetic",
            entrypoint="allocate", cli_args=None, db_path=None,
            input_files_json="{}", input_hashes_json="{}",
            total_students=0, total_allocated=0, total_unallocated=0,
            history_metrics_json=None, qa_summary_json=serialized,
            status=status, message=None,
        )
    )


def _snapshot(db: LocalDatabase, run_id: int, rule_status: str = "PASS", *,
              violations: int = 0, level: str = "error") -> None:
    details = pd.DataFrame(
        [{"rule_id": "QA_RULE_SAMPLE", "level": level} for _ in range(violations)]
    )
    db.insert_qa_snapshot(
        run_id=run_id,
        qa_summary_df=pd.DataFrame([{
            "rule_id": "QA_RULE_SAMPLE", "status": rule_status,
            "violations_count": violations,
        }]),
        qa_details_df=details,
    )


def test_missing_run_never_implies_qa_pass(db):
    health = compute_run_health("missing-run", db=db)
    assert (health.status, health.reason) == ("UNVERIFIED", "missing_run")
    assert "safe to use" not in health.summary_text


def test_run_without_any_qa_is_not_recorded(db):
    health = compute_run_health(str(_run(db)), db=db)
    assert (health.status, health.reason) == ("UNVERIFIED", "not_recorded")
    assert health.counts == {"P0": 0, "P1": 0, "P2": 0}


@pytest.mark.parametrize("payload", [
    "{not-valid-json",
    '{"passed": "true", "violation_count": 0}',
    '{"passed": true}',
    '{"passed": true, "violation_count": -1}',
    '{"passed": true, "violation_count": 0.5}',
])
def test_invalid_overall_qa_is_never_pass(db, payload):
    run_id = _run(db, outcome=payload)
    _snapshot(db, run_id)
    health = compute_run_health(str(run_id), db=db)
    assert (health.status, health.reason) == ("UNVERIFIED", "invalid")


def test_unreadable_snapshot_not_treated_as_clean(db):
    run_id = _run(db, outcome={"passed": True, "violation_count": 0})
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO qa_snapshots (run_id, qa_summary_json) VALUES (?, ?)",
            (run_id, "{broken"),
        )
        conn.commit()
    health = compute_run_health(str(run_id), db=db)
    assert (health.status, health.reason) == ("UNVERIFIED", "invalid")
    report = build_llm_debug_report(str(run_id), db=db)
    assert report["health"]["status"] == "UNVERIFIED"
    assert report["health"]["reason"] == "invalid"


def test_positive_qa_requires_a_complete_saved_rule_summary(db):
    run_id = _run(db, outcome={"passed": True, "violation_count": 0})
    health = compute_run_health(str(run_id), db=db)
    assert (health.status, health.reason) == ("UNVERIFIED", "incomplete")


def test_failed_run_without_qa_is_not_qa_pass(db):
    run_id = _run(db, status="failed")
    health = compute_run_health(str(run_id), db=db)
    assert (health.status, health.reason) == ("ERROR", "run_failed")
    assert "failed" in health.summary_text.lower()


def test_explicit_qa_pass_only_certifies_recorded_qa(db):
    run_id = _run(db, outcome={"passed": True, "violation_count": 0})
    _snapshot(db, run_id)
    health = compute_run_health(str(run_id), db=db)
    assert (health.status, health.reason) == ("OK", None)
    assert "output file not independently verified" in health.summary_text
    assert "safe to use" not in health.summary_text


def test_explicit_qa_failure_is_not_overridden_by_zero_counts(db):
    run_id = _run(db, outcome={"passed": False, "violation_count": 0})
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR"
    assert health.counts["P0"] == 0


@pytest.mark.parametrize(("level", "expect"), [
    ("error", "ERROR"), ("warning", "WARN"),
])
def test_recorded_snapshot_violation_remains_actionable_without_overall(db, level, expect):
    run_id = _run(db)
    _snapshot(
        db, run_id,
        rule_status="FAIL" if level == "error" else "WARN",
        violations=1, level=level,
    )
    health = compute_run_health(str(run_id), db=db)
    assert health.status == expect


def test_separately_stored_qa_summary_cannot_create_unearned_pass(db):
    run_id = _run(db)
    db.insert_qa_summary([QaSummaryRow(
        run_id=run_id, violation_code="TOTAL", severity="info", count=0
    )])
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "UNVERIFIED"


def test_separately_stored_material_violation_is_not_ignored(db):
    run_id = _run(db)
    db.insert_qa_summary([QaSummaryRow(
        run_id=run_id, violation_code="SYNTHETIC", severity="P0", count=1
    )])
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR"
    assert health.counts["P0"] == 1


def test_snapshot_failure_overrides_contradictory_aggregate_pass(db):
    run_id = _run(db, outcome={"passed": True, "violation_count": 0})
    _snapshot(db, run_id, rule_status="FAIL", violations=0)
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR"


def test_warning_with_explicit_pass_retains_warning_severity(db):
    run_id = _run(db, outcome={"passed": True, "violation_count": 1})
    _snapshot(db, run_id, rule_status="WARN", violations=1, level="warning")
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "WARN"
    assert health.counts["P1"] == 1


def test_mismatched_overall_count_never_becomes_pass(db):
    run_id = _run(db, outcome={"passed": True, "violation_count": 2})
    _snapshot(db, run_id)
    health = compute_run_health(str(run_id), db=db)
    assert (health.status, health.reason) == ("UNVERIFIED", "incomplete")
