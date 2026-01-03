import argparse
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from app.core.allocate_students import AllocationBatchResult, TraceDebugFrames
from app.core.policy_loader import load_policy
from app.core.qa.invariants import QaReport, QaRuleResult, run_all_invariants
from app.infra import cli
from app.infra.excel.export_qa_validation import QaValidationContext, export_qa_validation
from app.infra.history_store import QaOutcome, build_run_context, log_allocation_run
from app.infra.local_database import LocalDatabase


def _history_violation_report() -> QaReport:
    policy = load_policy()
    history_info_df = pd.DataFrame(
        {"national_code": ["1234567890", "1234567890"], "allocation_channel": ["SCHOOL", "SCHOOL"]}
    )
    return run_all_invariants(policy=policy, history_info=history_info_df)


def test_history_store_persists_join_key_duplicates(tmp_path: Path) -> None:
    db_path = Path(tmp_path) / "history.db"
    db = LocalDatabase(db_path)
    db.initialize()

    run_uuid = "uuid-test"
    now = datetime.now(UTC)
    ctx = build_run_context(
        command="build-matrix",
        cli_args="--test",
        policy_version="1.0.3",
        ssot_version="1.0.2",
        started_at=now,
        completed_at=now,
        success=True,
        message="ok",
        input_students=None,
        input_pool=None,
        output=None,
        policy_path=None,
        total_students=None,
        allocated_students=None,
        unallocated_students=None,
    )
    qa_report = QaReport(
        results=[QaRuleResult(rule_id="QA_RULE_STU_01", passed=True, violations=[])]
    )
    duplicates_df = pd.DataFrame(
        {
            "کدرشته": [1, 1],
            "جنسیت": [0, 0],
            "دانش آموز فارغ": [0, 0],
            "مرکز گلستان صدرا": [0, 0],
            "مالی حکمت بنیاد": [0, 0],
            "کد مدرسه": [10, 10],
            "mentor_id": ["EMP-1", "EMP-1"],
            "duplicate_group_size": [2, 2],
            "pool_row_index": [0, 2],
            "pool_source": ["inspactor", "inspactor"],
        }
    )
    qa_report.extras = {"pool_join_key_duplicates": duplicates_df}
    qa_outcome = QaOutcome(passed=True, violation_count=0)

    log_allocation_run(
        run_uuid=run_uuid,
        ctx=ctx,
        history_metrics=None,
        qa_outcome=qa_outcome,
        qa_report=qa_report,
        trace_snapshot=None,
        qa_extras=None,
        db=db,
    )

    qa_summary, qa_details, qa_extras = db.fetch_qa_snapshot(run_id=1)
    assert qa_summary is not None
    assert qa_details is not None
    assert "pool_join_key_duplicates" in qa_extras
    restored = qa_extras["pool_join_key_duplicates"].reset_index(drop=True)
    assert list(restored.columns) == list(duplicates_df.columns)
    assert restored.equals(duplicates_df.reset_index(drop=True))


def test_history_store_persists_history_rule(tmp_path: Path) -> None:
    db_path = Path(tmp_path) / "history.db"
    db = LocalDatabase(db_path)
    db.initialize()

    run_uuid = "uuid-history"
    now = datetime.now(UTC)
    ctx = build_run_context(
        command="allocate",
        cli_args="--test",
        policy_version="1.0.3",
        ssot_version="1.0.2",
        started_at=now,
        completed_at=now,
        success=False,
        message="history violation",
        input_students=None,
        input_pool=None,
        output=None,
        policy_path=None,
        total_students=None,
        allocated_students=None,
        unallocated_students=None,
    )

    qa_report = _history_violation_report()
    qa_outcome = QaOutcome(passed=qa_report.passed, violation_count=len(qa_report.violations))

    log_allocation_run(
        run_uuid=run_uuid,
        ctx=ctx,
        history_metrics=None,
        qa_outcome=qa_outcome,
        qa_report=qa_report,
        trace_snapshot=None,
        qa_extras=None,
        db=db,
    )

    qa_summary, qa_details, _ = db.fetch_qa_snapshot(run_id=1)
    assert qa_summary is not None
    assert qa_details is not None

    history_rows = qa_summary[qa_summary["rule_id"] == "QA_RULE_HISTORY_CHANNEL_01"]
    assert not history_rows.empty
    detail_rows = qa_details[qa_details["rule_id"] == "QA_RULE_HISTORY_CHANNEL_01"]
    assert not detail_rows.empty


def test_history_rule_present_in_qa_workbook(tmp_path: Path) -> None:
    qa_report = _history_violation_report()
    output = Path(tmp_path) / "qa.xlsx"

    export_qa_validation(
        report=qa_report,
        output=output,
        context=QaValidationContext(),
    )

    summary_sheet = pd.read_excel(output, sheet_name="summary")
    history_rows = summary_sheet[summary_sheet["rule_id"] == "QA_RULE_HISTORY_CHANNEL_01"]
    assert not history_rows.empty
    assert history_rows.iloc[0]["status"] == "FAIL"


def test_allocate_cli_passes_history_info_into_qa(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    policy = load_policy()
    history_info_df = pd.DataFrame(
        {"national_code": ["1234567890", "1234567890"], "allocation_channel": ["SCHOOL", "SCHOOL"]}
    )

    def fake_inject_student_ids(
        students_df: pd.DataFrame, args: argparse.Namespace, policy: object
    ) -> tuple[pd.Series, dict[str, int], pd.DataFrame]:
        ids = pd.Series(["s-1"] * len(students_df))
        students_with_ids = students_df.copy()
        students_with_ids["student_id"] = ids
        students_with_ids["__source_index__"] = pd.RangeIndex(len(students_df))
        return ids, {}, students_with_ids

    def fake_allocate_batch(*_: object, **__: object) -> AllocationBatchResult:
        allocations = pd.DataFrame(
            {"student_id": ["s-1"], "mentor_id": ["m-1"], "__source_index__": [0]}
        )
        updated_pool = pd.DataFrame({"mentor_id": ["m-1"]})
        logs = pd.DataFrame({"student_id": ["s-1"]})
        trace = pd.DataFrame({"student_id": ["s-1"]})
        trace.attrs["history_info_df"] = history_info_df
        return AllocationBatchResult(
            allocations_df=allocations,
            pool_output=updated_pool,
            logs_df=logs,
            trace_df=trace,
            trace_extras=TraceDebugFrames(
                summary_df=None,
                unallocated_summary=None,
                policy_violations=None,
                final_status_counts=None,
            ),
        )

    def fake_selection_reasons(*_: object, **__: object) -> pd.DataFrame:
        return pd.DataFrame({"dummy": [1]})

    def fake_selection_sheet(
        df: pd.DataFrame, writer: object | None = None, policy: object | None = None
    ) -> tuple[str, pd.DataFrame]:
        return "selection_reasons", df

    class _DummyAudit:
        def __init__(self) -> None:
            self.audit_frame = pd.DataFrame()

    def fake_validate_join_keys(*_: object, **__: object) -> _DummyAudit:
        return _DummyAudit()

    def fake_audit_sheet(*_: object, **__: object) -> pd.DataFrame:
        return pd.DataFrame()

    captured: dict[str, pd.DataFrame | None] = {"history_info": None}

    class CaptureHistoryInfoError(Exception):
        pass

    def fake_run_all_invariants(**kwargs: object) -> object:
        captured["history_info"] = cast(pd.DataFrame | None, kwargs.get("history_info"))
        raise CaptureHistoryInfoError()

    monkeypatch.setattr(cli, "_inject_student_ids", fake_inject_student_ids)
    monkeypatch.setattr(cli.cli_legacy, "_inject_student_ids", fake_inject_student_ids)
    monkeypatch.setattr(cli, "allocate_batch", fake_allocate_batch)
    monkeypatch.setattr(cli.cli_legacy, "allocate_batch", fake_allocate_batch)
    monkeypatch.setattr(cli, "build_selection_reason_rows", fake_selection_reasons)
    monkeypatch.setattr(cli.cli_legacy, "build_selection_reason_rows", fake_selection_reasons)
    monkeypatch.setattr(cli, "write_selection_reasons_sheet", fake_selection_sheet)
    monkeypatch.setattr(cli.cli_legacy, "write_selection_reasons_sheet", fake_selection_sheet)
    monkeypatch.setattr(cli, "validate_allocation_join_keys", fake_validate_join_keys)
    monkeypatch.setattr(cli.cli_legacy, "validate_allocation_join_keys", fake_validate_join_keys)
    monkeypatch.setattr(cli, "build_join_key_audit_sheet", fake_audit_sheet)
    monkeypatch.setattr(cli.cli_legacy, "build_join_key_audit_sheet", fake_audit_sheet)
    monkeypatch.setattr(cli, "build_join_key_summary_sheet", fake_audit_sheet)
    monkeypatch.setattr(cli.cli_legacy, "build_join_key_summary_sheet", fake_audit_sheet)
    monkeypatch.setattr(
        cli, "build_sabt_export_frame", lambda *args, **kwargs: pd.DataFrame({"student_id": ["s-1"]})
    )
    monkeypatch.setattr(
        cli.cli_legacy,
        "build_sabt_export_frame",
        lambda *args, **kwargs: pd.DataFrame({"student_id": ["s-1"]}),
    )
    monkeypatch.setattr(cli, "run_all_invariants", fake_run_all_invariants)
    monkeypatch.setattr(cli.cli_legacy, "run_all_invariants", fake_run_all_invariants)

    args = argparse.Namespace(
        _raw_argv=[],
        _ui_overrides={},
        export_profile=None,
        export_profile_path=None,
        sabt_output=None,
        center_manager=None,
        center_managers=None,
        center_priority=None,
        strict_manager_validation=False,
        golestan_manager=None,
        sadra_manager=None,
        academic_year=1402,
    )

    students_base = pd.DataFrame(
        {
            "کدرشته": [1],
            "جنسیت": [0],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [10],
            "national_id": ["1234567890"],
            "gender": ["M"],
        }
    )
    pool_base = pd.DataFrame({"mentor_id": ["m-1"], "remaining_capacity": [1]})

    with pytest.raises(CaptureHistoryInfoError):
        cli._allocate_and_write(
            students_base,
            pool_base,
            args=args,
            policy=policy,
            progress=lambda *_: None,
            output=tmp_path / "alloc.xlsx",
            capacity_column=policy.columns.remaining_capacity,
            db=None,
            command_name="allocate",
            input_students_path=None,
            input_pool_path=None,
            policy_path=tmp_path / "policy.json",
        )

    assert captured["history_info"] is not None
    assert_frame_equal(captured["history_info"], history_info_df)
