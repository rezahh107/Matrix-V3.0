from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas import ExcelFile

from app.core.policy_loader import load_policy
from app.core.qa.invariants import run_all_invariants
from app.infra.excel.export_qa_validation import QaValidationContext, export_qa_validation


def _build_pool_row(mentor_id: int, policy_columns: list[str], *, seed: int = 1) -> dict[str, int]:
    base = {"mentor_id": mentor_id, "کد کارمندی پشتیبان": mentor_id, "remaining_capacity": 1}
    for index, column in enumerate(policy_columns):
        base[column] = seed + index
    return base


def test_export_qa_pool_conflicts_empty_frame(tmp_path: Path) -> None:
    policy = load_policy()
    join_keys = policy.join_keys
    pool = pd.DataFrame(
        [_build_pool_row(1, join_keys, seed=10), _build_pool_row(2, join_keys, seed=20)]
    )

    report = run_all_invariants(policy=policy, pool=pool)
    pool_conflicts = report.extras.get("pool_join_conflicts") if report.extras else None
    assert pool_conflicts is not None
    assert pool_conflicts.empty

    output = tmp_path / "qa_no_conflicts.xlsx"
    context = QaValidationContext(pool_join_conflicts=pool_conflicts)
    export_qa_validation(report=report, output=output, context=context)

    xls = ExcelFile(output)
    assert "pool_join_conflicts" in xls.sheet_names
    conflicts_sheet = pd.read_excel(output, sheet_name="pool_join_conflicts")
    assert conflicts_sheet.empty
    summary = pd.read_excel(output, sheet_name="summary")
    status = summary.loc[summary["rule_id"] == "QA_RULE_POOL_JOIN_01", "status"].iat[0]
    assert status == "PASS"


def test_export_qa_pool_conflicts_detects_conflict(tmp_path: Path) -> None:
    policy = load_policy()
    join_keys = policy.join_keys
    conflict_row = _build_pool_row(5, join_keys, seed=30)
    conflict_row[join_keys[0]] = 999
    pool = pd.DataFrame(
        [
            _build_pool_row(5, join_keys, seed=10),
            conflict_row,
        ]
    )

    report = run_all_invariants(policy=policy, pool=pool)
    pool_conflicts = report.extras.get("pool_join_conflicts") if report.extras else None
    assert pool_conflicts is not None
    assert not pool_conflicts.empty
    assert int(pool_conflicts.loc[0, "mentor_id"]) == 5

    output = tmp_path / "qa_with_conflicts.xlsx"
    context = QaValidationContext(pool_join_conflicts=pool_conflicts)
    export_qa_validation(report=report, output=output, context=context)

    conflicts_sheet = pd.read_excel(output, sheet_name="pool_join_conflicts")
    assert not conflicts_sheet.empty
    summary = pd.read_excel(output, sheet_name="summary")
    status = summary.loc[summary["rule_id"] == "QA_RULE_POOL_JOIN_01", "status"].iat[0]
    assert status == "FAIL"
