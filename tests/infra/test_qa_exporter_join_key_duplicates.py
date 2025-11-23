from pathlib import Path

import pandas as pd

from app.core.qa.invariants import QaReport
from app.infra.excel.export_qa_validation import QaValidationContext, export_qa_validation


def test_qa_exporter_writes_join_key_duplicate_sheet(tmp_path) -> None:
    report = QaReport(results=[])
    duplicates = pd.DataFrame(
        {
            "کدرشته": [1],
            "جنسیت": [0],
            "دانش آموز فارغ": [0],
            "مرکز گلستان صدرا": [0],
            "مالی حکمت بنیاد": [0],
            "کد مدرسه": [10],
            "mentor_id": ["EMP-1"],
            "duplicate_group_size": [2],
            "pool_row_index": [0],
            "pool_source": ["inspactor"],
        }
    )
    ctx = QaValidationContext(pool_join_key_duplicates=duplicates)
    output = Path(tmp_path) / "qa.xlsx"

    export_qa_validation(report=report, output=output, context=ctx)

    excel = pd.ExcelFile(output)
    assert "pool_join_key_duplicates" in excel.sheet_names
    restored = excel.parse("pool_join_key_duplicates")
    assert restored.loc[0, "mentor_id"] == "EMP-1"
