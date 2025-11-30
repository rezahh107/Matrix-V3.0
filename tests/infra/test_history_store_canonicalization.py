from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from app.infra.history_store import (
    QaOutcome,
    build_run_context,
    canonicalize_national_code,
    log_allocation_run,
)
from app.infra.local_database import LocalDatabase


class _FailingDatabase(LocalDatabase):
    def __init__(self, path: Path) -> None:
        super().__init__(path)

    def initialize(self) -> None:  # type: ignore[override]
        raise RuntimeError("db unavailable")


def test_canonicalize_national_code_normalizes_and_pads() -> None:
    assert canonicalize_national_code(" 123-456-789 ") == "0123456789"
    assert canonicalize_national_code("0001234567") == "0001234567"
    assert canonicalize_national_code("abc") is None


def test_canonicalize_national_code_trims_to_last_ten_digits() -> None:
    assert canonicalize_national_code("12345678901") == "2345678901"
    assert canonicalize_national_code("۰۰۱۲۳۴۵۶۷۸۹۰") == "1234567890"


def test_log_allocation_run_handles_db_failure(tmp_path) -> None:
    db = _FailingDatabase(tmp_path / "history.db")
    now = datetime.now(UTC)
    ctx = build_run_context(
        command="alloc",
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
    history_info = pd.DataFrame(
        {"کد ملی": ["12345678901", "۰۰۱۲۳۴۵۶۷۸۹۰"], "allocation_channel": ["school", "SADRA"]}
    )
    trace_df = pd.DataFrame({"student_id": [1]})
    trace_df.attrs["history_info_df"] = history_info

    log_allocation_run(
        run_uuid="uuid-test",
        ctx=ctx,
        history_metrics=None,
        qa_outcome=QaOutcome(passed=True, violation_count=0),
        qa_report=None,
        trace_snapshot=trace_df,
        qa_extras=None,
        db=db,
    )

    # No exception should propagate; data normalization should occur even when DB fails
    normalized = trace_df.attrs["history_info_df"]
    assert normalized.loc[0, "کد ملی"] == "2345678901"
    assert normalized.loc[1, "کد ملی"] == "1234567890"
