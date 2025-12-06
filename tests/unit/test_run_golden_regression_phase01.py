from __future__ import annotations

import pandas as pd
import pytest

from scripts.run_golden_regression_phase01 import (
    GoldenRegressionError,
    _canonicalize_pool,
    _compare_frames,
    _issues_to_frame,
)


def test_canonicalize_pool_sorts_and_validates() -> None:
    unsorted = pd.DataFrame(
        {
            "group_code": [2, 1],
            "gender": [1, 0],
            "graduation_status": [1, 1],
            "center": [0, 0],
            "finance": [0, 0],
            "school_code": [0, 0],
            "mentor_id": [20, 10],
        }
    )

    canonical = _canonicalize_pool(unsorted)
    assert canonical.loc[0, "mentor_id"] == 10
    assert canonical.loc[1, "mentor_id"] == 20

    with pytest.raises(GoldenRegressionError):
        _canonicalize_pool(unsorted.drop(columns=["mentor_id"]))


def test_issues_to_frame_sorts_and_includes_fields() -> None:
    class DummyIssue:
        def __init__(
            self, entity_type: str, row_index: int, column: str, raw_value: object, error_code: str
        ) -> None:
            self.entity_type = entity_type
            self.row_index = row_index
            self.column = column
            self.raw_value = raw_value
            self.error_code = error_code

    issues = _issues_to_frame(
        [
            DummyIssue("mentor", 2, "finance", "", "DATA_MISSING"),
            DummyIssue("mentor", 1, "group_code", 7, "DATA_INVALID"),
        ]
    )

    assert list(issues.columns) == [
        "entity_type",
        "row_index",
        "column",
        "raw_value",
        "error_code",
    ]
    assert issues.loc[0, "row_index"] == 1
    assert issues.loc[1, "row_index"] == 2

    empty = _issues_to_frame([])
    assert empty.empty


def test_compare_frames_detects_drift() -> None:
    expected = pd.DataFrame({"a": [1], "b": [2]})
    current = pd.DataFrame({"a": [1], "b": [2]})
    _compare_frames("sample", expected, current)

    with pytest.raises(GoldenRegressionError):
        _compare_frames("sample", expected, pd.DataFrame({"a": [1]}))

    with pytest.raises(GoldenRegressionError):
        _compare_frames("sample", expected, pd.DataFrame({"a": [1], "b": [3]}))
