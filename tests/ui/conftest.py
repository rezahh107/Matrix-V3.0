from __future__ import annotations

import contextlib
import gc
from typing import Any

import pytest

try:
    # Import Qt modules eagerly to detect missing system dependencies (e.g.,
    # libGL) and skip the entire UI test suite instead of failing collection.
    from PySide6 import QtCore as _QtCore, QtGui as _QtGui, QtWidgets as _QtWidgets  # noqa: F401
except Exception as exc:  # pragma: no cover - defensive skip for CI images without Qt
    pytest.skip(f"PySide6 unavailable or incomplete: {exc}", allow_module_level=True)

# Windows CI skip removed after stabilizing the loader harness cleanup. Qt UI
# tests now run on all platforms to keep coverage consistent.

_TEST_QSETTINGS_ORGANIZATION = "MatrixV3Tests"
_TEST_QSETTINGS_APPLICATION = "MatrixV3UI"


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

    previous_application_name = app.applicationName()
    previous_organization_name = app.organizationName()
    app.setOrganizationName(_TEST_QSETTINGS_ORGANIZATION)
    app.setApplicationName(_TEST_QSETTINGS_APPLICATION)

    try:
        yield app
    finally:
        thread_pool_cls.globalInstance().waitForDone(2000)
        app.closeAllWindows()
        app.processEvents()
        app.sendPostedEvents()
        app.processEvents()
        app.setApplicationName(previous_application_name)
        app.setOrganizationName(previous_organization_name)
        gc.collect()


def _dispose_test_windows(qapp, preexisting_windows):
    """Destroy only windows created during this test, including hidden/closed ones.

    Closing a QWidget is not destruction unless WA_DeleteOnClose is enabled.
    Retain pre-test top-level windows and the shared QApplication. Never delete
    an owner while any of its QThreads are still running.
    """
    from PySide6.QtCore import QEvent, Qt, QThread
    from shiboken6 import isValid

    retained_ids = {id(window) for window in preexisting_windows}
    test_windows = [
        window for window in qapp.topLevelWidgets()
        if isValid(window) and id(window) not in retained_ids
    ]
    unsafe_windows = []
    refused_windows = []
    for window in test_windows:
        if not isValid(window):
            continue
        # close() may immediately destroy WA_DeleteOnClose widgets, including
        # their running child QThreads, before the safety check below can run.
        # Keep closeEvent (and its normal Worker shutdown) but own deletion here.
        delete_on_close = window.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if delete_on_close:
            window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        try:
            closed = window.close()
        finally:
            if delete_on_close and isValid(window):
                window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        if not isValid(window):
            continue
        owned_threads = list(window.findChildren(QThread))
        worker = getattr(window, "_worker", None)
        if isinstance(worker, QThread):
            owned_threads.append(worker)
        owned_threads.extend(
            loader for loader in (getattr(window, "_excel_loaders", ()) or ())
            if isinstance(loader, QThread)
        )
        if any(isValid(thread) and thread.isRunning() for thread in owned_threads):
            unsafe_windows.append(type(window).__name__)
            continue
        if not closed:
            refused_windows.append(type(window).__name__)
            continue
        window.deleteLater()

    qapp.processEvents()
    qapp.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()
    gc.collect()
    remaining = [
        type(window).__name__ for window in test_windows if isValid(window)
    ]
    if unsafe_windows:
        pytest.fail(
            f"Refusing to destroy windows with running QThreads: {unsafe_windows}"
        )
    if refused_windows:
        pytest.fail(f"Test-owned Qt windows refused to close: {refused_windows}")
    if remaining:
        pytest.fail(f"Test-owned Qt windows survived teardown: {remaining}")


@pytest.fixture(autouse=True)
def _isolate_default_qsettings(qapp):
    from PySide6.QtCore import QSettings

    # Some test modules override the session qapp fixture. QSettings() needs
    # valid Qt application identity in *every* test, including those modules:
    # on Windows an unnamed application can fail opening its native registry key.
    previous_application_name = qapp.applicationName()
    previous_organization_name = qapp.organizationName()
    qapp.setOrganizationName(_TEST_QSETTINGS_ORGANIZATION)
    qapp.setApplicationName(_TEST_QSETTINGS_APPLICATION)

    try:
        # Strong references prevent wrapper identity reuse within the test.
        preexisting_windows = tuple(qapp.topLevelWidgets())
        settings = QSettings()
        assert settings.status() == QSettings.Status.NoError, settings.fileName()
        settings.clear()
        settings.sync()
        assert settings.status() == QSettings.Status.NoError, settings.fileName()

        yield

        _dispose_test_windows(qapp, preexisting_windows)

        settings = QSettings()
        assert settings.status() == QSettings.Status.NoError, settings.fileName()
        settings.clear()
        settings.sync()
        assert settings.status() == QSettings.Status.NoError, settings.fileName()
    finally:
        qapp.setApplicationName(previous_application_name)
        qapp.setOrganizationName(previous_organization_name)


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

    def mouseClick(self, widget: Any, button: Any, *, delay: int = 0) -> None:  # noqa: N802
        from PySide6.QtTest import QTest

        QTest.mouseClick(widget, button, delay=delay)

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
