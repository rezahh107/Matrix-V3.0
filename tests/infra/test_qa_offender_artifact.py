from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.core.policy_loader import load_policy
from app.core.qa.invariants import QaReport, check_MENTOR_TYPE_01
from app.infra.cli_legacy import _fingerprint_offenders, _write_mentor_type_offenders_artifact


def _build_report_with_school_code_issues() -> QaReport:
    policy = load_policy()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "کد کارمندی پشتیبان": ["S2", "S1"],
            "جایگزین": ["S2", "S1"],
            "عادی مدرسه": ["مدرسه‌ای", "مدرسه‌ای"],
            school_col: [pd.NA, 0],
            "source_sheet": ["SheetB", "SheetA"],
            "source_row_index": [5, 2],
        }
    )
    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)
    return QaReport(results=[result])


def test_mentor_type_offender_artifact_written(tmp_path: Path) -> None:
    report = _build_report_with_school_code_issues()
    output = tmp_path / "matrix.xlsx"

    artifact = _write_mentor_type_offenders_artifact(report, output=output)

    assert artifact is not None
    artifact_path, offender_count = artifact
    assert offender_count == 2
    assert artifact_path == tmp_path / "artifacts" / "qa_offenders.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["rule_id"] == "QA_RULE_MENTOR_TYPE_01"
    assert "generated_at" in payload
    assert payload["offender_count"] == 2
    assert isinstance(payload["data_fingerprint"], str)
    offenders = payload["offenders"]
    assert offenders[0]["source_sheet"] == "SheetA"
    assert offenders[0]["source_row_index"] == 2
    assert offenders[0]["mentor_id"] == "S1"
    assert offenders[1]["source_sheet"] == "SheetB"
    assert offenders[1]["source_row_index"] == 5
    assert payload["data_fingerprint"] == _fingerprint_offenders(offenders)


def test_mentor_type_offender_artifact_is_deterministic(tmp_path: Path) -> None:
    report = _build_report_with_school_code_issues()
    output = tmp_path / "matrix.xlsx"

    first = _write_mentor_type_offenders_artifact(report, output=output)
    assert first is not None
    payload_first = json.loads((tmp_path / "artifacts" / "qa_offenders.json").read_text())
    payload_first.pop("generated_at", None)

    second = _write_mentor_type_offenders_artifact(report, output=output)
    assert second is not None
    payload_second = json.loads((tmp_path / "artifacts" / "qa_offenders.json").read_text())
    payload_second.pop("generated_at", None)

    assert payload_first == payload_second


def test_mentor_type_offender_artifact_skips_when_no_offenders(tmp_path: Path) -> None:
    policy = load_policy()
    school_col = policy.columns.school_code
    matrix = pd.DataFrame(
        {
            "کد کارمندی پشتیبان": ["M1"],
            "جایگزین": ["5000"],
            "عادی مدرسه": ["عادی"],
            school_col: [pd.NA],
        }
    )
    result = check_MENTOR_TYPE_01(matrix=matrix, policy=policy)
    report = QaReport(results=[result])

    artifact = _write_mentor_type_offenders_artifact(report, output=tmp_path / "matrix.xlsx")

    assert artifact is None
