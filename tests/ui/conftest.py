from __future__ import annotations

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
        from PySide6.QtTest import QSignalSpy

        spy = QSignalSpy(signal)
        if not spy.wait(timeout or 1000):
            raise TimeoutError(f"Signal did not emit within {timeout or 1000} ms")
        return spy

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
