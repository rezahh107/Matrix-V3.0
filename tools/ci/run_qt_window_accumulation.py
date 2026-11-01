"""Disposable Windows Qt creation/cleanup experiment; never used by product CI.

Compare close() alone and close()+deleteLater() under fresh Python processes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import gc
from pathlib import Path

from PySide6.QtCore import QEvent, QSettings
from PySide6.QtWidgets import QApplication

from app.ui.main_window import MainWindow
from app.ui.theme import apply_global_font
from tools.ci.qt_windows_lifecycle_probe import _qt_snapshot
from tests.ui.conftest import _dispose_test_windows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", choices=["close-only", "delete-later", "fixture"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("MatrixV3Diagnostic")
    app.setApplicationName("QtWindowAccumulation")
    settings = QSettings()
    settings.clear()
    settings.sync()
    rows = []
    for iteration in range(args.iterations):
        start = time.monotonic()
        preexisting_windows = tuple(app.topLevelWidgets())
        window = MainWindow()
        construction = round(time.monotonic() - start, 4)
        window.resize(960, 640)
        window.show()
        app.processEvents()
        after_create = _qt_snapshot()
        window.close()
        if args.cleanup == "delete-later":
            window.deleteLater()
        elif args.cleanup == "fixture":
            _dispose_test_windows(app, preexisting_windows)
        del window
        app.processEvents()
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        gc.collect()
        after_cleanup = _qt_snapshot()
        font_start = time.monotonic()
        apply_global_font(app)
        font_elapsed = round(time.monotonic() - font_start, 4)
        row = {
            "iteration": iteration + 1,
            "cleanup": args.cleanup,
            "construction_seconds": construction,
            "font_reapply_seconds": font_elapsed,
            "widgets_after_create": after_create.get("live_widgets"),
            "widgets_after_cleanup": after_cleanup.get("live_widgets"),
            "windows_after_cleanup": after_cleanup.get("live_top_level_windows"),
            "active_workers": after_cleanup.get("window_running_workers"),
            "working_set_after_cleanup": after_cleanup.get("working_set_bytes"),
            "snapshot_error": after_cleanup.get("snapshot_error"),
        }
        rows.append(row)
        print("ITERATION", json.dumps(row), flush=True)
        args.output.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    print("PROBE_DONE", args.cleanup, len(rows), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
