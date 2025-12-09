from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_golden_regression import (
    MENTOR_ISSUE_COLUMNS,
    GoldenRegressionError,
    _load_expected_mentor_issues_frame,
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
