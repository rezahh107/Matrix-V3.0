from pathlib import Path

import pandas as pd

from app.infra.local_database import LocalDatabase
from app.infra.year_database_manager import YearDatabaseManager


def test_year_database_manager_creates_isolated_db(tmp_path: Path) -> None:
    manager = YearDatabaseManager(tmp_path)
    db = manager.create_year("1403-1404")
    db.initialize()
    assert db.get_academic_year() == "1403-1404"

    tables = db.list_tables_with_counts()
    assert "runs" in set(tables["table"])


def test_year_manager_lists_versions(tmp_path: Path) -> None:
    manager = YearDatabaseManager(tmp_path)
    manager.create_year("1402-1403")
    infos = manager.list_years()
    assert infos
    assert infos[0].schema_version is not None
