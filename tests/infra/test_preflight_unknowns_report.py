from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.infra.cli_legacy import (
    _build_unknowns_report,
    collect_unknown_issues,
    compute_preflight_exit_code,
)
from app.infra.io_utils import write_json_report


def test_preflight_unknowns_report(tmp_path: Path) -> None:
    policy = load_policy(Path("config/policy.json"))
    join_keys = list(policy.join_keys)
    students_df = pd.DataFrame({join_keys[0]: [1]})
    pool_df = pd.DataFrame({join_keys[0]: [1]})

    issues, blocking = collect_unknown_issues(
        students_df=students_df,
        pool_df=pool_df,
        policy=policy,
    )
    report = _build_unknowns_report(issues, policy=policy, sample_limit=3)
    report_path = tmp_path / "reports" / "unknown_data_report.json"
    write_json_report(report_path, report)

    loaded = json.loads(report_path.read_text(encoding="utf-8"))
    assert loaded["summary"]["total"] == len(issues)
    assert len(loaded["issues"]) == len(issues)
    assert loaded["summary"]["by_entity_type"]["student"] >= 1
    assert compute_preflight_exit_code(issues, policy=policy, blocking=blocking) == 3
