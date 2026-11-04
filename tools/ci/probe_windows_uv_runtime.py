"""Bounded Windows uv source runtime probe; no real student/mentor inputs."""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from contextlib import closing
from importlib.metadata import version
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings, QThread
from shiboken6 import isValid

from app.infra.local_database import LocalDatabase
from app.infra.logging import _resolve_logging_paths
from app.main import __version__, load_main_window, setup_application
from app.ui.fonts import _register_embedded_vazirmatn
from app.utils.path_utils import get_log_directory, get_user_data_dir, resource_path


def _verify_directory_io(directory: Path) -> None:
    """Prove create/write/read/delete on the actual filesystem, not via is_dir()."""

    payload = b"matrix-uv-directory-io-probe"
    try:
        # delete-on-close also requires deletion rights on Windows. Even when a
        # write/read fails, the context manager closes and removes the file.
        with tempfile.NamedTemporaryFile(
            mode="w+b", prefix=".matrix-uv-io-", dir=directory
        ) as handle:
            probe_path = Path(handle.name)
            if handle.write(payload) != len(payload):
                raise RuntimeError(f"Incomplete directory probe write: {directory}")
            handle.flush()
            handle.seek(0)
            if handle.read() != payload:
                raise RuntimeError(f"Directory probe read-back mismatch: {directory}")
        if probe_path.exists():
            raise RuntimeError(f"Directory probe cleanup left a file: {probe_path}")
    except OSError as exc:
        raise RuntimeError(f"Application directory I/O qualification failed: {directory}") from exc


def _verify_application_directories() -> None:
    """Exercise operational file logs, error reports, and user-home crash storage."""

    # Use configure_logging's own resolver: the working-directory destination
    # must not be hidden by writable user-home folders.
    operational_logs, error_reports = _resolve_logging_paths()
    # Normal configure_logging creates these destinations before opening files.
    operational_logs.mkdir(parents=True, exist_ok=True)
    error_reports.mkdir(parents=True, exist_ok=True)
    for directory in (
        get_user_data_dir(),
        get_log_directory(),
        operational_logs,
        error_reports,
    ):
        _verify_directory_io(directory)


def main() -> None:
    if os.name != "nt":
        raise RuntimeError("Windows-only runtime qualification")
    assert __version__ == version("smart-student-allocation")
    expected_version = os.environ.get("MATRIX_EXPECTED_PACKAGE_VERSION")
    if expected_version and __version__ != expected_version:
        raise RuntimeError("Windows installed application version differs from candidate")
    for path in (
        resource_path("config", "policy.json"),
        resource_path("resources", "translations", "ui_texts.json"),
        resource_path("app", "ui", "styles.qss"),
    ):
        if not path.is_file():
            raise RuntimeError(f"Missing application resource: {path}")
    json.loads(resource_path("config", "policy.json").read_text(encoding="utf-8"))
    _verify_application_directories()
    with tempfile.TemporaryDirectory(prefix="matrix-ci-db-") as work:
        db_path = Path(work) / "references.sqlite"
        # LocalDatabase tracks open SQLite handles; closing its context is
        # essential before Windows can remove the isolated temporary folder.
        with LocalDatabase(db_path) as db:
            db.initialize()
            with closing(sqlite3.connect(db_path)) as conn:
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
