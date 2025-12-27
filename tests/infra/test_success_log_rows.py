from __future__ import annotations

import pandas as pd

from app.infra.cli_legacy import _get_success_log_rows


def test_success_log_rows_missing_status_returns_all_rows() -> None:
    logs_df = pd.DataFrame({"student_id": ["S-1", "S-2"], "mentor_id": [1, 2]})

    success_rows = _get_success_log_rows(logs_df)

    assert success_rows["student_id"].tolist() == ["S-1", "S-2"]
    assert success_rows["mentor_id"].tolist() == [1, 2]


def test_success_log_rows_is_case_insensitive() -> None:
    logs_df = pd.DataFrame(
        {
            "student_id": ["S-1", "S-2", "S-3", "S-4"],
            "allocation_status": ["Success", "FAILED", "SUCCESS", "success"],
        }
    )

    success_rows = _get_success_log_rows(logs_df)

    assert success_rows["student_id"].tolist() == ["S-1", "S-3", "S-4"]
