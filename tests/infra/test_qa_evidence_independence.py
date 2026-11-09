"""PR#54 F1: negative QA evidence survives a malformed sibling in SQLite."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.infra.errors import DatabaseOperationError
from app.infra.health import build_llm_debug_report, compute_run_health
from app.infra.local_database import LocalDatabase, QaSummaryRow, RunRecord


@pytest.fixture
def db(tmp_path: Path) -> Iterator[LocalDatabase]:
    database = LocalDatabase(tmp_path / "qa-independence.db")
    database.initialize()
    yield database
    database.close_all_connections()


def _run(
    db: LocalDatabase, outcome: dict[str, object] | str | None = None, status: str = "success"
) -> int:
    now = datetime.now(UTC)
    return db.insert_run(RunRecord(
        run_uuid="synthetic", started_at=now, finished_at=now,
        policy_version="synthetic", ssot_version="synthetic",
        entrypoint="allocate", cli_args=None, db_path=None,
        input_files_json="{}", input_hashes_json="{}",
        total_students=0, total_allocated=0, total_unallocated=0,
        history_metrics_json=None,
        qa_summary_json=json.dumps(outcome) if isinstance(outcome, dict) else outcome,
        status=status, message=None,
    ))


def _snapshot(
    db: LocalDatabase, run_id: int, level: str = "P0", rule_status: str = "WARN"
) -> None:
    db.insert_qa_snapshot(
        run_id=run_id,
        qa_summary_df=pd.DataFrame([{
            "rule_id": "SYNTHETIC_RULE", "status": rule_status,
            "violations_count": 1,
        }]),
        qa_details_df=pd.DataFrame([{
            "rule_id": "SYNTHETIC_RULE", "level": level, "student_id": 17,
        }]),
    )


def _corrupt(db: LocalDatabase, run_id: int, column: str, payload: str) -> None:
    assert column in {"qa_summary_json", "qa_details_json", "qa_extras_json"}
    with db.connect() as connection:
        connection.execute(
            f"UPDATE qa_snapshots SET {column} = ? WHERE run_id = ?",
            (payload, run_id),
        )
        connection.commit()


@pytest.mark.parametrize(
    ("broken_part", "level", "expected", "bucket"),
    [
        ("summary_shape", "P0", "ERROR", "P0"),
        ("qa_summary_json", "critical", "ERROR", "P0"),
        ("qa_extras_json", "P0", "ERROR", "P0"),
        ("qa_extras_json", "warn", "WARN", "P1"),
    ],
)
def test_negative_details_survive_independent_corruption(
    db: LocalDatabase, broken_part: str, level: str, expected: str, bucket: str
) -> None:
    run_id = _run(db, {"passed": True, "violation_count": 1})
    _snapshot(db, run_id, level)
    if broken_part == "summary_shape":
        db.insert_qa_snapshot(
            run_id=run_id,
            qa_summary_df=pd.DataFrame([{
                "rule_id": "SYNTHETIC_RULE", "status": "WARN",
            }]),
            qa_details_df=pd.DataFrame([{
                "rule_id": "SYNTHETIC_RULE", "level": level, "student_id": 17,
            }]),
        )
    else:
        _corrupt(db, run_id, broken_part, "{corrupt")
    health = compute_run_health(str(run_id), db=db)
    assert health.status == expected
    assert health.counts[bucket] == 1
    assert health.issues_summary[0].severity == bucket


def test_readable_fail_row_survives_corrupt_details(db: LocalDatabase) -> None:
    run_id = _run(db, {"passed": True, "violation_count": 1})
    _snapshot(db, run_id, rule_status="FAIL")
    _corrupt(db, run_id, "qa_details_json", "{corrupt")
    assert compute_run_health(str(run_id), db=db).status == "ERROR"


def test_malformed_row_preceding_fail_still_preserves_explicit_fail(db: LocalDatabase) -> None:
    run_id = _run(db, {"passed": True, "violation_count": 0})
    db.insert_qa_snapshot(
        run_id=run_id,
        qa_summary_df=pd.DataFrame([
            {"rule_id": "BROKEN", "status": "UNKNOWN", "violations_count": 0},
            {"rule_id": "SYNTHETIC_RULE", "status": "FAIL", "violations_count": 0},
        ]),
        qa_details_df=pd.DataFrame(columns=["rule_id", "level"]),
    )
    assert compute_run_health(str(run_id), db=db).status == "ERROR"


def test_unreadable_extras_cannot_authorize_clean_pass(db: LocalDatabase) -> None:
    run_id = _run(db, {"passed": True, "violation_count": 0})
    db.insert_qa_snapshot(
        run_id=run_id,
        qa_summary_df=pd.DataFrame([{
            "rule_id": "SYNTHETIC_RULE", "status": "PASS", "violations_count": 0,
        }]),
        qa_details_df=pd.DataFrame(columns=["rule_id", "level"]),
    )
    assert compute_run_health(str(run_id), db=db).status == "OK"
    _corrupt(db, run_id, "qa_extras_json", "{corrupt")
    health = compute_run_health(str(run_id), db=db)
    assert (health.status, health.reason) == ("UNVERIFIED", "invalid")


def test_strict_snapshot_reader_still_detects_corrupt_extras(db: LocalDatabase) -> None:
    run_id = _run(db, {"passed": True, "violation_count": 1})
    _snapshot(db, run_id)
    _corrupt(db, run_id, "qa_extras_json", "{corrupt")
    with pytest.raises(DatabaseOperationError):
        db.fetch_qa_snapshot(run_id, strict=True)
    summary, details, extras, invalid = db._fetch_qa_snapshot_evidence(run_id)
    assert len(summary) == len(details) == 1
    assert extras == {} and invalid == frozenset({"qa_extras_json"})


def test_debug_report_retains_p0_and_detail_samples_with_corrupt_extras(
    db: LocalDatabase,
) -> None:
    run_id = _run(db, {"passed": True, "violation_count": 1})
    _snapshot(db, run_id)
    _corrupt(db, run_id, "qa_extras_json", "{corrupt")
    report = build_llm_debug_report(str(run_id), db=db)
    assert report["health"]["status"] == "ERROR"
    assert report["health"]["counts"]["P0"] == 1
    assert report["issues_summary"][0]["severity"] == "P0"
    assert report["samples"][0]["rows"] == [{"student_id": 17}]
    assert report["extras"] == []


def test_bad_legacy_row_does_not_hide_following_valid_p0(db: LocalDatabase) -> None:
    run_id = _run(db)
    db.insert_qa_summary([
        QaSummaryRow(run_id=run_id, violation_code="BAD", severity="info", count=-1),
        QaSummaryRow(run_id=run_id, violation_code="P0", severity="critical", count=1),
    ])
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR"
    assert health.counts["P0"] == 1


def test_same_rule_mixed_levels_counted_in_correct_buckets(db: LocalDatabase) -> None:
    run_id = _run(db, {"passed": True, "violation_count": 2})
    db.insert_qa_snapshot(
        run_id=run_id,
        qa_summary_df=pd.DataFrame([{
            "rule_id": "SYNTHETIC_RULE", "status": "WARN", "violations_count": 2,
        }]),
        qa_details_df=pd.DataFrame([
            {"rule_id": "SYNTHETIC_RULE", "level": "P0"},
            {"rule_id": "SYNTHETIC_RULE", "level": "P1"},
        ]),
    )
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR"
    assert health.counts == {"P0": 1, "P1": 1, "P2": 0}


@pytest.mark.parametrize("outcome", [None, "{invalid-json", {"passed": False, "violation_count": 1}])
def test_missing_invalid_or_failed_outcome_cannot_erase_p0(
    db: LocalDatabase, outcome: dict[str, object] | str | None
) -> None:
    run_id = _run(db, outcome)
    _snapshot(db, run_id)
    _corrupt(db, run_id, "qa_extras_json", "{corrupt")
    assert compute_run_health(str(run_id), db=db).status == "ERROR"


def test_failed_run_remains_error(db: LocalDatabase) -> None:
    run_id = _run(db, status="failed")
    assert compute_run_health(str(run_id), db=db).status == "ERROR"

@pytest.mark.parametrize("missing_table", ["qa_summary", "qa_snapshots"])
def test_sqlite_sibling_query_failure_does_not_hide_independent_p0(
    db: LocalDatabase, missing_table: str
) -> None:
    run_id = _run(db, {"passed": True, "violation_count": 1})
    _snapshot(db, run_id)
    db.insert_qa_summary([
        QaSummaryRow(run_id=run_id, violation_code="P0", severity="P0", count=1),
    ])
    with db.connect() as connection:
        connection.execute(f"DROP TABLE {missing_table}")
        connection.commit()
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR" and health.counts["P0"] == 1
    report = build_llm_debug_report(str(run_id), db=db)
    assert report["health"]["status"] == "ERROR"
    assert report["health"]["counts"]["P0"] == 1


@pytest.mark.parametrize("missing_table", ["qa_summary", "qa_snapshots"])
def test_unreadable_sibling_table_never_earns_clean_pass(
    db: LocalDatabase, missing_table: str
) -> None:
    run_id = _run(db, {"passed": True, "violation_count": 0})
    db.insert_qa_snapshot(
        run_id=run_id,
        qa_summary_df=pd.DataFrame([{
            "rule_id": "SYNTHETIC_RULE", "status": "PASS", "violations_count": 0,
        }]),
        qa_details_df=pd.DataFrame(columns=["rule_id", "level"]),
    )
    assert compute_run_health(str(run_id), db=db).status == "OK"
    with db.connect() as connection:
        connection.execute(f"DROP TABLE {missing_table}")
        connection.commit()
    health = compute_run_health(str(run_id), db=db)
    assert (health.status, health.reason) == ("UNVERIFIED", "invalid")
