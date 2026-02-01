from pathlib import Path

import pandas as pd
import pytest

from app.infra.errors import DatabasePreparationError
from app.infra.local_database import LocalDatabase
from app.infra.references.schools import import_school_report_from_excel


@pytest.mark.parametrize(
    ("columns", "missing_column"),
    [
        ({"کد مدرسه": [1]}, "نام مدرسه"),
        ({"نام مدرسه": ["A"]}, "کد مدرسه"),
    ],
)
def test_school_report_import_rejects_missing_required_columns(
    tmp_path: Path,
    columns: dict[str, list[object]],
    missing_column: str,
) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    df = pd.DataFrame(columns)
    path = tmp_path / "school_report.xlsx"
    df.to_excel(path, index=False)

    with pytest.raises(DatabasePreparationError) as excinfo:
        import_school_report_from_excel(path, db)

    message = excinfo.value.reason or ""
    assert "ستون‌های الزامی مدارس" in message
    assert missing_column in (excinfo.value.hint or "")


def test_school_report_import_allows_missing_optional_columns(
    tmp_path: Path,
) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    df = pd.DataFrame({"کد مدرسه": [1], "نام مدرسه": ["A"]})
    path = tmp_path / "school_report.xlsx"
    df.to_excel(path, index=False)

    normalized = import_school_report_from_excel(path, db)

    assert set(normalized.columns).issuperset({"کد مدرسه", "نام مدرسه"})
