from pathlib import Path

import pytest

try:  # pragma: no cover - محیط CI ممکن است وابستگی Qt نداشته باشد
    from PySide6.QtWidgets import QApplication, QMessageBox
except Exception:  # pragma: no cover - fallback for headless env
    QApplication = None  # type: ignore
    QMessageBox = None  # type: ignore

from app.infra.local_database import _SCHEMA_VERSION, LocalDatabase
from app.infra.year_database_manager import YearDatabaseInfo
from app.ui.database_manager_dialog import _QT_AVAILABLE, DatabaseManagerDialog


@pytest.fixture(scope="module")
def qapp():
    if QApplication is None or not _QT_AVAILABLE:
        pytest.skip("Qt bindings not available")
    app = QApplication.instance() or QApplication([])
    yield app


def test_database_manager_dialog_shows_counts_and_path(tmp_path: Path, qapp: QApplication) -> None:
    if QApplication is None or not _QT_AVAILABLE:
        pytest.skip("Qt bindings not available")
    db = LocalDatabase(tmp_path / "sample.sqlite", academic_year="test-year")
    db.initialize()
    info = YearDatabaseInfo("test-year", db.path, schema_version=_SCHEMA_VERSION, size_bytes=db.path.stat().st_size)
    dialog = DatabaseManagerDialog(db=db, year_info=info)
    assert str(db.path) in dialog._path_label.text()
    assert dialog._counts_table.rowCount() >= 1


def test_database_manager_dialog_shows_schema_issue(tmp_path: Path, qapp: QApplication) -> None:
    if QApplication is None or not _QT_AVAILABLE:
        pytest.skip("Qt bindings not available")
    db_path = tmp_path / "broken.sqlite"
    with LocalDatabase(db_path).connect() as conn:
        conn.execute(
            "CREATE TABLE students_cache(\"کد ملی\" TEXT)"
        )
        conn.execute(
            """
            CREATE TABLE schema_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                schema_version INTEGER NOT NULL,
                policy_version TEXT NOT NULL,
                ssot_version TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "INSERT INTO schema_meta (id, schema_version, policy_version, ssot_version, created_at)"
            " VALUES (1, 9, '1.0.0', '1.0.0', strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))"
        )
        conn.commit()
    db = LocalDatabase(db_path)
    info = YearDatabaseInfo("test-year", db.path, schema_version=_SCHEMA_VERSION, size_bytes=db.path.stat().st_size)
    dialog = DatabaseManagerDialog(db=db, year_info=info)
    # ستون student_id باید به‌عنوان مفقود گزارش شود
    issue_rows = [dialog._issues_table.item(r, 1).text() for r in range(dialog._issues_table.rowCount())]
    assert any("student_id" in text for text in issue_rows)


def test_database_manager_buttons_trigger_actions(tmp_path: Path, qapp: QApplication, monkeypatch) -> None:
    if QApplication is None or not _QT_AVAILABLE:
        pytest.skip("Qt bindings not available")
    db = LocalDatabase(tmp_path / "to_reset.sqlite")
    db.initialize()
    info = YearDatabaseInfo("current", db.path, schema_version=_SCHEMA_VERSION, size_bytes=0)
    dialog = DatabaseManagerDialog(db=db, year_info=info)
    monkeypatch.setattr("app.ui.database_manager_dialog.QMessageBox.information", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.ui.database_manager_dialog.QMessageBox.critical", lambda *args, **kwargs: None)
    monkeypatch.setattr("app.ui.database_manager_dialog.QMessageBox.question", lambda *args, **kwargs: QMessageBox.Yes)

    calls = {"full": 0, "cache": 0}
    monkeypatch.setattr(db, "reset_full_database", lambda: calls.__setitem__("full", calls["full"] + 1) or db.path)
    monkeypatch.setattr(db, "clear_caches", lambda: calls.__setitem__("cache", calls["cache"] + 1))

    dialog._btn_full_reset.click()
    dialog._btn_clear_cache.click()

    assert calls["full"] == 1
    assert calls["cache"] == 1


def test_full_reset_error_shows_message_box(tmp_path: Path, qapp: QApplication, monkeypatch) -> None:
    if QApplication is None or not _QT_AVAILABLE:
        pytest.skip("Qt bindings not available")
    db = LocalDatabase(tmp_path / "to_reset_error.sqlite")
    db.initialize()
    info = YearDatabaseInfo("current", db.path, schema_version=_SCHEMA_VERSION, size_bytes=0)
    dialog = DatabaseManagerDialog(db=db, year_info=info)
    monkeypatch.setattr("app.ui.database_manager_dialog.QMessageBox.question", lambda *args, **kwargs: QMessageBox.Yes)
    captured = {}

    def _raise_error():
        raise RuntimeError("boom")

    monkeypatch.setattr(db, "reset_full_database", _raise_error)

    def _capture(*args, **kwargs):
        captured["called"] = True
        return None

    monkeypatch.setattr("app.ui.database_manager_dialog.QMessageBox.critical", _capture)
    monkeypatch.setattr("app.ui.database_manager_dialog.QMessageBox.information", lambda *args, **kwargs: None)

    dialog._full_reset()

    assert captured.get("called")
