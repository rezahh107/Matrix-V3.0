from __future__ import annotations

import contextlib
import gc
from typing import Any

import pytest


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
    """Wait for a Qt signal using the Qt event loop (no Python threads).

    Returns the captured signal arguments as a list of tuples. Raises a pytest
    failure on timeout to keep tests deterministic and avoid native aborts.
    """

    from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

    if QCoreApplication.instance() is None:
        pytest.fail("waitSignal called without an active Q(Core)Application")

    loop = QEventLoop()
    timeout_ms = 1000 if timeout is None else timeout
    args: list[tuple[Any, ...]] = []
    timed_out = False

    def _on_emitted(*signal_args: Any) -> None:
        args.append(tuple(signal_args))
        loop.quit()

    def _on_timeout() -> None:
        nonlocal timed_out
        timed_out = True
        loop.quit()

    signal.connect(_on_emitted)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(_on_timeout)
    timer.start(timeout_ms)

    loop.exec()

    with contextlib.suppress(Exception):
        signal.disconnect(_on_emitted)
    timer.stop()

    if timed_out:
        pytest.fail(f"Timed out after {timeout_ms} ms waiting for signal {signal}")
    return args


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
