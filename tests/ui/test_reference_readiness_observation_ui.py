"""Real Qt entrypoints must not repair or conceal missing SQLite references."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd
import pytest

from app.infra.groupcode.groupcode_repository import GroupCodeRepository
from app.infra.schools.school_repository import SchoolRepository
from app.infra.year_database_manager import YearDatabaseManager


def _reference_rows(path: Path) -> tuple[object, ...]:
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as conn:
        groups = conn.execute("SELECT * FROM groupcodes ORDER BY group_code").fetchall()
        meta = conn.execute(
            "SELECT * FROM reference_meta WHERE table_name IN ('schools', 'groupcodes') "
            "ORDER BY table_name"
        ).fetchall()
    return (tuple(groups), tuple(meta))


def test_mainwindow_startup_database_refresh_and_allocate_observe_missing_groups(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from app.ui import main_window_base
    from app.ui.main_window import MainWindow

    manager = YearDatabaseManager(tmp_path / "years")
    db = manager.open_year("current")
    pd.DataFrame(
        {"کد مدرسه": [1], "نام مدرسه": ["Synthetic"], "مرکز گلستان صدرا": [0], "جنسیت": [1]}
    ).to_excel(tmp_path / "schools.xlsx", index=False)
    SchoolRepository(db).import_from_excel(tmp_path / "schools.xlsx")
    pd.DataFrame(
        {"group_code": [24], "level": ["متوسطه دوم"], "grade": [10], "track": ["ریاضی"]}
    ).to_excel(tmp_path / "groups.xlsx", index=False)
    GroupCodeRepository(db).import_from_excel(tmp_path / "groups.xlsx")
    with db.connect() as conn:
        conn.execute("DELETE FROM groupcodes")
        conn.commit()
    db.close_all_connections()
    before = _reference_rows(db.path)

    monkeypatch.setattr(
        main_window_base,
        "YearDatabaseManager",
        lambda _root: YearDatabaseManager(tmp_path / "years"),
    )
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, _title, detail: warnings.append(str(detail))),
    )
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        app.processEvents()
        assert window._groupcode_repository is not None
        assert window._groupcode_repository.status().row_count == 0
        assert window._database_tab is not None
        window._database_tab.refresh_status()
        placeholder = window._database_tab._t("database.placeholder", "Not connected yet")
        assert window._database_tab._groupcodes_status_label.text() == placeholder
        assert _reference_rows(db.path) == before

        window._start_allocate()
        assert warnings, "Missing reference must block Allocate with actionable warning"
        assert window._worker is None
        assert _reference_rows(db.path) == before
    finally:
        window.close()
        if window._local_db is not None:
            window._local_db.close_all_connections()
