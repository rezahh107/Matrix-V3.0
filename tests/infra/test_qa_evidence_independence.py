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


def _grouping_snapshot(
    db: LocalDatabase,
    *,
    details: list[dict[str, object]],
    status: str = "WARN",
    summary_rule: object = "R",
    passed: bool = True,
) -> int:
    """Persist the real split-frame QA snapshot with the existing SQLite API."""
    run_id = _run(db, outcome={"passed": passed, "violation_count": len(details)})
    db.insert_qa_snapshot(
        run_id=run_id,
        qa_summary_df=pd.DataFrame([{
            "rule_id": summary_rule, "status": status,
            "violations_count": len(details),
        }]),
        qa_details_df=pd.DataFrame(
            details, columns=["rule_id", "level", "student_id"]
        ),
    )
    return run_id


def _grouping_rows(bad_id: object, *, reversed_order: bool = False) -> list[dict[str, object]]:
    valid = {"rule_id": "R", "level": "P0", "student_id": 11}
    malformed = {"rule_id": bad_id, "level": "P2", "student_id": 12}
    return [malformed, valid] if reversed_order else [valid, malformed]


@pytest.mark.parametrize("reversed_order", [False, True])
def test_grouping_valid_p0_survives_bad_identifier(
    db: LocalDatabase, reversed_order: bool
) -> None:
    run_id = _grouping_snapshot(
        db, details=_grouping_rows(["BROKEN"], reversed_order=reversed_order)
    )
    _, restored, _ = db.fetch_qa_snapshot(run_id, strict=True)
    assert restored is not None
    assert any(isinstance(value, list) for value in restored["rule_id"])

    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR"
    assert health.counts["P0"] == 1
    assert health.counts["P1"] == 0
    assert len(health.issues_summary) == 1
    assert (
        health.issues_summary[0].issue_code,
        health.issues_summary[0].severity,
        health.issues_summary[0].count,
    ) == ("R", "P0", 1)
    report = build_llm_debug_report(str(run_id), db=db)
    assert report["health"]["status"] == "ERROR"
    assert report["health"]["counts"]["P0"] == 1
    assert report["samples"] == [{"issue_code": "R", "rows": [{"student_id": 11}]}]


@pytest.mark.parametrize("bad_id", [
    {"nested": "BROKEN"}, 123, True, None, "", "   ", ["BROKEN", "NESTED"],
])
def test_grouping_unsupported_identities_do_not_hide_valid_p0(
    db: LocalDatabase, bad_id: object
) -> None:
    run_id = _grouping_snapshot(db, details=_grouping_rows(bad_id))
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR"
    assert health.counts["P0"] == 1
    assert [issue.issue_code for issue in health.issues_summary] == ["R"]


def test_grouping_both_identifiers_valid_retains_all_counts_and_samples(
    db: LocalDatabase,
) -> None:
    run_id = _grouping_snapshot(db, details=_grouping_rows("BROKEN"))
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR"
    assert health.counts == {"P0": 1, "P1": 0, "P2": 1}
    assert {(i.issue_code, i.severity) for i in health.issues_summary} == {
        ("R", "P0"), ("BROKEN", "P2"),
    }
    report = build_llm_debug_report(str(run_id), db=db)
    assert {s["issue_code"] for s in report["samples"]} == {"R", "BROKEN"}


def test_grouping_bad_identifier_and_corrupt_extras_keep_valid_p0(
    db: LocalDatabase,
) -> None:
    run_id = _grouping_snapshot(db, details=_grouping_rows(["BROKEN"]))
    _corrupt(db, run_id, "qa_extras_json", "{malformed")
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR" and health.counts["P0"] == 1
    report = build_llm_debug_report(str(run_id), db=db)
    assert report["health"]["counts"]["P0"] == 1
    assert report["samples"] == [{"issue_code": "R", "rows": [{"student_id": 11}]}]


def test_grouping_malformed_only_cannot_earn_ok(db: LocalDatabase) -> None:
    run_id = _grouping_snapshot(
        db, details=[{"rule_id": ["BROKEN"], "level": "P2", "student_id": 12}],
        status="PASS",
    )
    health = compute_run_health(str(run_id), db=db)
    assert (health.status, health.reason) == ("UNVERIFIED", "invalid")
    assert health.issues_summary == []


def test_grouping_complete_qa_pass_stays_ok(db: LocalDatabase) -> None:
    run_id = _grouping_snapshot(db, details=[], status="PASS")
    health = compute_run_health(str(run_id), db=db)
    assert (health.status, health.reason) == ("OK", None)
    assert health.counts == {"P0": 0, "P1": 0, "P2": 0}


def test_grouping_mixed_p0_p1_severities_stay_distinct(db: LocalDatabase) -> None:
    run_id = _grouping_snapshot(db, details=[
        {"rule_id": "R", "level": "critical", "student_id": 11},
        {"rule_id": "R", "level": "warn", "student_id": 12},
    ])
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR"
    assert health.counts == {"P0": 1, "P1": 1, "P2": 0}
    assert health.issues_summary[0].count == 2


def test_grouping_p1_survives_bad_identifier(db: LocalDatabase) -> None:
    run_id = _grouping_snapshot(db, details=[
        {"rule_id": "R", "level": "P1", "student_id": 11},
        {"rule_id": {"nested": 5}, "level": "P2", "student_id": 12},
    ])
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "WARN"
    assert health.counts["P1"] == 1
    assert [i.issue_code for i in health.issues_summary] == ["R"]


def test_grouping_invalid_summary_id_does_not_hide_valid_p0(
    db: LocalDatabase,
) -> None:
    run_id = _grouping_snapshot(
        db, details=[{"rule_id": "R", "level": "P0", "student_id": 11}],
        summary_rule=["BROKEN"],
    )
    health = compute_run_health(str(run_id), db=db)
    assert health.status == "ERROR"
    assert health.counts["P0"] == 1
    assert [i.issue_code for i in health.issues_summary] == ["R"]


def test_grouping_invalid_summary_id_never_authorizes_pass(
    db: LocalDatabase,
) -> None:
    run_id = _grouping_snapshot(
        db, details=[], status="PASS", summary_rule={"bad": True}
    )
    health = compute_run_health(str(run_id), db=db)
    assert (health.status, health.reason) == ("UNVERIFIED", "invalid")


def test_grouping_explicit_fail_survives_bad_detail_identifier(
    db: LocalDatabase,
) -> None:
    run_id = _grouping_snapshot(
        db, details=[{"rule_id": ["BROKEN"], "level": "P2", "student_id": 12}],
        status="FAIL", passed=False,
    )
    assert compute_run_health(str(run_id), db=db).status == "ERROR"
