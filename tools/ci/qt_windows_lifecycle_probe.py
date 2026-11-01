"""Observe Qt lifecycle at pytest boundaries; never mutate tested Qt state.

Diagnostic branch only. JSONL contains code test IDs and aggregate counts, not data.
"""
from __future__ import annotations

import atexit
import ctypes
import gc
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import pytest

_PATH: Path | None = None
_STARTED: dict[str, float] = {}


def _write(kind: str, **fields: Any) -> None:
    if _PATH is None:
        return
    payload = {"kind": kind, "wall_time": time.time(), "monotonic": time.monotonic(), **fields}
    with _PATH.open("a", encoding="utf-8") as out:
        out.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")
        out.flush()
        os.fsync(out.fileno())


def _working_set_bytes() -> int | None:
    if sys.platform != "win32":
        return None

    class _Counters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_uint32),
            ("PageFaultCount", ctypes.c_uint32),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    try:
        counters = _Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32]
        psapi.GetProcessMemoryInfo.restype = ctypes.c_int
        if psapi.GetProcessMemoryInfo(
            kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
        ):
            return int(counters.WorkingSetSize)
    except Exception:
        pass
    return None


def _qt_snapshot() -> dict[str, Any]:
    snapshot: dict[str, Any] = {
        "working_set_bytes": _working_set_bytes(),
        "python_threads": threading.active_count(),
        "gc_counts": list(gc.get_count()),
        "process_cpu_seconds": round(time.process_time(), 3),
    }
    try:
        from PySide6.QtCore import QThread, QThreadPool
        from PySide6.QtWidgets import QApplication
        from shiboken6 import isValid

        app = QApplication.instance()
        if not isinstance(app, QApplication):
            snapshot["qapplication"] = False
            return snapshot
        widgets = QApplication.allWidgets()
        windows = QApplication.topLevelWidgets()
        valid_windows = [w for w in windows if isValid(w)]
        threads = [t for t in app.findChildren(QThread) if isValid(t)]
        workers = []
        for window in valid_windows:
            for attr in ("_worker",):
                worker = getattr(window, attr, None)
                if worker is not None and isValid(worker):
                    workers.append(worker)
            for worker in getattr(window, "_excel_loaders", ()) or ():
                if isValid(worker):
                    workers.append(worker)
        snapshot.update({
            "qapplication": True,
            "live_widgets": sum(bool(isValid(w)) for w in widgets),
            "live_top_level_windows": len(valid_windows),
            "visible_top_level_windows": sum(bool(w.isVisible()) for w in valid_windows),
            "qapp_owned_qthreads": len(threads),
            "qapp_owned_running_qthreads": sum(bool(t.isRunning()) for t in threads),
            "window_workers": len(workers),
            "window_running_workers": sum(bool(w.isRunning()) for w in workers),
            "global_pool_active": QThreadPool.globalInstance().activeThreadCount(),
        })
    except Exception as exc:
        snapshot["snapshot_error"] = type(exc).__name__ + ": " + str(exc)[:180]
    return snapshot


def pytest_configure(config: pytest.Config) -> None:
    global _PATH
    filename = os.environ.get("MATRIX_QT_PROBE_JSONL")
    if not filename:
        return
    _PATH = Path(filename)
    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _write("probe_configured", python=sys.version.split()[0], executable=sys.executable,
           platform=sys.platform, pid=os.getpid())
    atexit.register(lambda: _write("python_atexit", working_set_bytes=_working_set_bytes()))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None):
    start = time.monotonic()
    _write("test_start", test=item.nodeid, **_qt_snapshot())
    yield
    _write("test_end", test=item.nodeid,
           elapsed_seconds=round(time.monotonic() - start, 3), **_qt_snapshot())


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    _write("test_report", test=report.nodeid, phase=report.when, outcome=report.outcome,
           duration_seconds=round(report.duration, 3))


def pytest_sessionfinish(session: pytest.Session, exitstatus: pytest.ExitCode | int) -> None:
    _write("pytest_sessionfinish", logical_exitstatus=int(exitstatus), **_qt_snapshot())


def pytest_unconfigure(config: pytest.Config) -> None:
    _write("pytest_unconfigure", **_qt_snapshot())
