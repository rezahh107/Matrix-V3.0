from pathlib import Path

import pandas as pd
import pytest

from app.infra.errors import DatabasePreparationError
from app.infra.local_database import LocalDatabase
from app.infra.references.schools import import_school_report_from_excel


def test_school_report_import_rejects_missing_required_columns(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    df = pd.DataFrame(
        {
            "کد مدرسه": [1],
            "نام مدرسه": ["A"],
            "مرکز گلستان صدرا": [10],
            # "جنسیت" is intentionally missing
        }
    )
    path = tmp_path / "school_report.xlsx"
    df.to_excel(path, index=False)

    with pytest.raises(DatabasePreparationError) as excinfo:
        import_school_report_from_excel(path, db)

    assert "جنسیت" in (excinfo.value.hint or "")
