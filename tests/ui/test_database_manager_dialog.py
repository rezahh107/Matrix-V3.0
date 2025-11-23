from pathlib import Path

import pytest
try:  # pragma: no cover - محیط CI ممکن است وابستگی Qt نداشته باشد
    from PySide6.QtWidgets import QApplication
except Exception:  # pragma: no cover - fallback for headless env
    QApplication = None  # type: ignore

from app.infra.local_database import LocalDatabase
from app.infra.year_database_manager import YearDatabaseInfo
from app.ui.database_manager_dialog import DatabaseManagerDialog, _QT_AVAILABLE


@pytest.fixture(scope="module")
def qapp():
    if QApplication is None or not _QT_AVAILABLE:
        pytest.skip("Qt bindings not available")
    app = QApplication.instance() or QApplication([])
    yield app


def test_database_manager_dialog_shows_tables(tmp_path: Path, qapp: QApplication) -> None:
    if QApplication is None or not _QT_AVAILABLE:
        pytest.skip("Qt bindings not available")
    db = LocalDatabase(tmp_path / "sample.sqlite", academic_year="test-year")
    with db.connect() as conn:
        conn.execute("CREATE TABLE demo(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO demo(name) VALUES ('a'), ('b')")
        conn.commit()
    db.initialize()
    info = YearDatabaseInfo("test-year", db.path, schema_version=8, size_bytes=db.path.stat().st_size)
    dialog = DatabaseManagerDialog(db=db, year_info=info)
    dialog._refresh_tables()
    assert dialog.table_widget.rowCount() >= 1
    dialog.table_widget.selectRow(0)
    dialog._load_preview()
    assert dialog.preview_widget.columnCount() >= 1
