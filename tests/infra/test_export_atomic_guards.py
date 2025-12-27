import re
from pathlib import Path

import pandas as pd
import pytest

from app.core.policy_loader import load_policy
from app.infra.cli_legacy import (
    AllocationConsistencyError,
    _validate_and_write_allocation_workbook,
)


def test_export_guard_failure_prevents_output_file(tmp_path: Path) -> None:
    policy = load_policy()
    output = tmp_path / "out.xlsx"

    allocations_df = pd.DataFrame({"student_id": ["S-1"], "mentor_id": [100]})
    logs_df = pd.DataFrame(
        {
            "student_id": ["S-2"],
            "mentor_id": [200],
            "allocation_status": ["success"],
        }
    )

    sheets = {"allocations": allocations_df, "logs": logs_df}

    with pytest.raises(AllocationConsistencyError):
        _validate_and_write_allocation_workbook(
            sheets=sheets,
            header_overrides={},
            prepare_overrides={},
            output=output,
            policy=policy,
            allocations_df=allocations_df,
            logs_df=logs_df,
            join_key_audit=None,
            unallocated_summary=None,
            sabt_allocations_df=None,
        )

    assert not output.exists()


def test_export_layer_has_no_positional_student_id_attachment_patterns() -> None:
    banned = re.compile(r"\bstudent_id\b[^\n]*reindex\([^\n]*\.index", re.IGNORECASE)
    export_files = [
        Path("app/infra/cli_legacy.py"),
        Path("app/infra/excel/export_allocations.py"),
    ]

    for file_path in export_files:
        text = file_path.read_text(encoding="utf-8")
        assert not banned.search(text), f"Positional student_id attachment found in {file_path}"
