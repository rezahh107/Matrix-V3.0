"""Bounded Windows uv source runtime probe; no real student/mentor inputs."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from importlib.metadata import version
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, QThread
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.infra.local_database import LocalDatabase
from app.main import __version__, load_main_window, setup_application
from app.ui.fonts import _register_embedded_vazirmatn
from app.utils.path_utils import get_log_directory, get_user_data_dir, resource_path


def main() -> None:
    if os.name != "nt":
        raise RuntimeError("Windows-only runtime qualification")
    assert __version__ == version("smart-student-allocation")
    for path in (
        resource_path("config", "policy.json"),
        resource_path("resources", "translations", "ui_texts.json"),
        resource_path("app", "ui", "styles.qss"),
    ):
        if not path.is_file():
            raise RuntimeError(f"Missing application resource: {path}")
    json.loads(resource_path("config", "policy.json").read_text(encoding="utf-8"))
    if not get_user_data_dir().is_dir() or not get_log_directory().is_dir():
        raise RuntimeError("Application user/log directories not writable")
    with tempfile.TemporaryDirectory(prefix="matrix-ci-db-") as work:
        db_path = Path(work) / "references.sqlite"
        LocalDatabase(db_path).initialize()
        with sqlite3.connect(db_path) as conn:
            if not conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
            ).fetchone():
                raise RuntimeError("Local reference database schema not initialized")

    app = setup_application()
    families = _register_embedded_vazirmatn()
    if not any("vazir" in name.casefold() for name in families):
        raise RuntimeError(f"Embedded Persian font unavailable: {families}")
    settings = QSettings()  # Native Windows storage, same identity as real startup.
    key = "ci/uv-source-probe"
    try:
        settings.setValue(key, "writable")
        settings.sync()
        if settings.status() != QSettings.Status.NoError:
            raise RuntimeError(f"QSettings write failed: {settings.fileName()}")
        if QSettings().value(key) != "writable":
            raise RuntimeError("QSettings could not read its persisted key")
    finally:
        settings.remove(key)
        settings.sync()

    window = load_main_window()()
    window.show()
    app.processEvents()
    if not window.isVisible():
        raise RuntimeError("MainWindow was not shown")
    active_threads = [t for t in window.findChildren(QThread) if isValid(t) and t.isRunning()]
    if active_threads:
        raise RuntimeError("Unexpected active child QThreads before shutdown")
    if not window.close():
        raise RuntimeError("MainWindow refused graceful shutdown")
    app.processEvents()
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    if settings.status() != QSettings.Status.NoError:
        raise RuntimeError("QSettings error on shutdown")
    print(f"Windows uv source probe: window shown/closed; version={__version__}; "
          f"embedded_font={families}; QSettings=native-write-read; db=initialized")


if __name__ == "__main__":
    main()
