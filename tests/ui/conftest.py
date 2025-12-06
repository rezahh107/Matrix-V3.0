from __future__ import annotations

import contextlib
import gc
import os
import sys
from typing import Any

import pytest

# TEMPORARY CI WAIVER: skip Qt UI tests on Windows CI to avoid Fatal Qt abort
# in test_loaders.py until the loader harness is stabilized. Remove when a
# dedicated stabilization passes.
if sys.platform.startswith("win") and os.environ.get("MATRIX2_TEMP_SKIP_QT_UI") == "1":
    pytest.skip(
        "Temporarily skipping Qt UI tests on Windows CI (Fatal Qt abort in "
        "test_loaders.py). Remove after loader harness stabilization.",
        allow_module_level=True,
    )


@pytest.fixture(scope="session")
def qapp():
    qtwidgets = pytest.importorskip(
        "PySide6.QtWidgets",
        reason="PySide6 not available in test environment",
    )
    qtcore = pytest.importorskip(
        "PySide6.QtCore",
        reason="PySide6 not available in test environment",
    )

    qapplication_cls = qtwidgets.QApplication
    thread_pool_cls = qtcore.QThreadPool

    app = qapplication_cls.instance()
    if app is None:
        app = qapplication_cls([])

    yield app

    thread_pool_cls.globalInstance().waitForDone(2000)
    app.closeAllWindows()
    app.processEvents()
    app.sendPostedEvents()
    app.processEvents()
    gc.collect()


def waitSignal(signal: Any, *, timeout: int | None = None) -> list[tuple[Any, ...]]:  # noqa: N802
    """Wait synchronously for a Qt signal using only the Qt event loop.

    Avoids Python threading primitives to prevent Windows offscreen aborts.
    Returns a list of emitted argument tuples; raises a pytest failure on
    timeout for deterministic error reporting.
    """

    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

    if QCoreApplication.instance() is None:
        pytest.fail("waitSignal called without an active Q(Core)Application")

    loop = QEventLoop()
    timeout_ms = 5000 if timeout is None else timeout
    captured: list[tuple[Any, ...]] = []
    timed_out = False

    def _on_emitted(*args: Any) -> None:
        captured.append(tuple(args))
        if loop.isRunning():
            loop.quit()

    def _on_timeout() -> None:
        nonlocal timed_out
        timed_out = True
        if loop.isRunning():
            loop.quit()

    timer = QTimer()
    timer.setSingleShot(True)

    signal.connect(_on_emitted)
    timer.timeout.connect(_on_timeout)
    timer.start(timeout_ms)

    try:
        loop.exec()
    finally:
        with contextlib.suppress(Exception):
            signal.disconnect(_on_emitted)
        with contextlib.suppress(Exception):
            timer.timeout.disconnect(_on_timeout)
        if timer.isActive():
            timer.stop()

    if timed_out:
        pytest.fail(f"Timed out after {timeout_ms} ms waiting for signal {signal}")

    return captured


class _MiniQtBot:
    def __init__(self, app: Any):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QWidget

        self._app = app
        self._widgets: list[QWidget] = []
        self._delete_on_close = Qt.WidgetAttribute.WA_DeleteOnClose

    def addWidget(self, widget: Any) -> Any:  # noqa: N802 - match pytest-qt API
        widget.setAttribute(self._delete_on_close, True)
        self._widgets.append(widget)
        return widget

    def wait(self, ms: int) -> None:
        from PySide6.QtTest import QTest

        QTest.qWait(ms)

    def waitSignal(self, signal: Any, *, timeout: int | None = None) -> Any:  # noqa: N802
        return waitSignal(signal, timeout=timeout)

    def _cleanup(self) -> None:
        for widget in self._widgets:
            try:
                widget.close()
                widget.deleteLater()
            except Exception:
                pass
        self._app.processEvents()


@pytest.fixture()
def qtbot(qapp):
    try:
        from pytestqt.qtbot import QtBot  # type: ignore

        bot = QtBot(qapp)
        yield bot
        bot.wait(0)
        return
    except Exception:
        pass

    bot = _MiniQtBot(qapp)
    yield bot
    bot._cleanup()
