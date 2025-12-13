from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from app.infra.golden.regression_runner import (
    MENTOR_ISSUE_COLUMNS,
    GoldenRegressionError,
    _load_expected_mentor_issues_frame,
    _mentor_issues_frame,
)


def test_load_expected_mentor_issues_valid_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "expected_mentor_issues.csv"
    csv_path.write_text(
        "entity_type,row_index,column,raw_value,error_code\n"
        "mentor,1,جنسیت,پسر,INVALID_JOIN_VALUE\n",
        encoding="utf-8",
    )

    frame = _load_expected_mentor_issues_frame(csv_path)

    assert list(frame.columns) == MENTOR_ISSUE_COLUMNS
    assert len(frame.index) == 1
    assert frame.loc[0, "row_index"] == 1


def test_load_expected_mentor_issues_rejects_bad_row_length(tmp_path: Path) -> None:
    csv_path = tmp_path / "expected_mentor_issues.csv"
    csv_path.write_text(
        "entity_type,row_index,column,raw_value,error_code\n"
        "mentor,1,جنسیت,پسر\n",
        encoding="utf-8",
    )

    with pytest.raises(GoldenRegressionError) as excinfo:
        _load_expected_mentor_issues_frame(csv_path)

    assert "line 2" in str(excinfo.value)
    assert str(csv_path) in str(excinfo.value)


def test_load_expected_mentor_issues_rejects_bad_header(tmp_path: Path) -> None:
    csv_path = tmp_path / "expected_mentor_issues.csv"
    csv_path.write_text(
        "entity_type,row_index,column,error_code\n"
        "mentor,1,جنسیت,INVALID_JOIN_VALUE\n",
        encoding="utf-8",
    )

    with pytest.raises(GoldenRegressionError) as excinfo:
        _load_expected_mentor_issues_frame(csv_path)

    assert ",".join(MENTOR_ISSUE_COLUMNS) in str(excinfo.value)
    assert str(csv_path) in str(excinfo.value)


def test_phase02_script_imports_cleanly() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = f".{os.pathsep}{env.get('PYTHONPATH', '')}" if env.get("PYTHONPATH") else "."

    result = subprocess.run(
        [sys.executable, "scripts/run_golden_regression_phase02.py", "--help"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0
    assert "phase06 golden regression" in result.stdout


def test_mentor_issues_frame_normalizes_missing_raw_values() -> None:
    frame = pd.DataFrame(
        [
            ["mentor", 1, "col", "", "E1"],
            ["mentor", 2, "col", "nan", "E2"],
            ["mentor", 3, "col", "NaN", "E3"],
            ["mentor", 4, "col", None, "E4"],
        ],
        columns=MENTOR_ISSUE_COLUMNS,
    )

    normalized = _mentor_issues_frame(frame)

    assert normalized["raw_value"].isna().tolist() == [True, True, True, True]
