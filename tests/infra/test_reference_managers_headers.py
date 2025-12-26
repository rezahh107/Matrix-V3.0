from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.infra.local_database import LocalDatabase
from app.infra.reference_managers_repository import (
    import_managers_from_excel,
    load_managers_from_cache,
)


def test_manager_report_alias_headers_and_pii_drop(tmp_path: Path) -> None:
    db = LocalDatabase(tmp_path / "local.sqlite")
    df = pd.DataFrame(
        {
            "manager name": ["Ali"],
            "center code": [101],
            "phone": ["123"],
            "email": ["a@example.com"],
        }
    )
    path = tmp_path / "managers.xlsx"
    df.to_excel(path, index=False)

    normalized = import_managers_from_excel(path, db=db)

    assert "نام مدیر" in normalized.columns
    assert "مرکز گلستان صدرا" in normalized.columns
    cached = load_managers_from_cache(db=db)
    assert "phone" not in cached.columns
    assert "email" not in cached.columns
    assert int(cached.loc[0, "مرکز گلستان صدرا"]) == 101
