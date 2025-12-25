from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from app.core.qa.invariants import QaReport, QaRuleResult, QaViolation
from app.infra.cli import _build_qa_meta


def _make_report(passed: bool, rule_id: str) -> QaReport:
    violation = QaViolation(rule_id=rule_id, level="error", message="bad", details=None)
    result = QaRuleResult(
        rule_id=rule_id, passed=passed, violations=[violation] if not passed else []
    )
    return QaReport(results=[result])


def test_build_qa_meta_collects_counts() -> None:
    policy = SimpleNamespace(version="test-version")
    start = datetime(2024, 1, 1, tzinfo=UTC)
    end = datetime(2024, 1, 1, 0, 1, tzinfo=UTC)
    join_audit = pd.DataFrame({"any_mismatch": [True, False, True]})
    trace_df = pd.DataFrame({"student_id": [1, 2, 3]})
    trace_summary = pd.DataFrame({"student_id": [1, 2]})
    history_info = pd.DataFrame({"student_id": [1]})
    report = _make_report(False, "QA_RULE_TEST")

    meta = _build_qa_meta(
        run_uuid="uuid-1",
        command_name="allocate",
        policy=policy,  # type: ignore[arg-type]
        capacity_column="remaining_capacity",
        output=Path("/tmp/out.xlsx"),
        input_students_path=Path("/tmp/stu.xlsx"),
        input_pool_path=Path("/tmp/pool.xlsx"),
        started_at=start,
        completed_at=end,
        qa_report=report,
        join_key_audit=join_audit,
        trace_df=trace_df,
        trace_summary_df=trace_summary,
        history_info_df=history_info,
    )

    assert meta["qa_rules_total"] == 1
    assert meta["qa_rules_failed"] == 1
    assert meta["join_mismatches"] == 2
    assert meta["trace_rows"] == 3
    assert meta["trace_summary_rows"] == 2
    assert meta["history_info_rows"] == 1
    assert meta["duration_seconds"] == 60
