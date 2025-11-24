from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from app.core.qa.invariants import QaReport, QaRuleResult
from app.infra.history_store import QaOutcome, build_run_context, log_allocation_run
from app.infra.local_database import LocalDatabase


def test_history_store_persists_join_key_duplicates(tmp_path) -> None:
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
