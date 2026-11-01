"""Regression checks for per-test Qt window ownership and teardown."""

from __future__ import annotations

from threading import Event

import pytest
from PySide6.QtCore import QThread, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget
from shiboken6 import isValid

from app.ui.main_window import MainWindow
from tests.ui.conftest import _dispose_test_windows


def test_cleanup_destroys_visible_hidden_and_already_closed_windows(
    qapp: QApplication,
) -> None:
    # A pre-existing top-level window belongs to an outside fixture/session.
    retained = QWidget()
    preexisting = tuple(qapp.topLevelWidgets())
    visible, hidden, closed = QWidget(), QWidget(), QMainWindow()
    visible.show()
    closed.show()
    closed.close()
    assert all(isValid(w) for w in (visible, hidden, closed, retained))

    _dispose_test_windows(qapp, preexisting)

    assert all(not isValid(w) for w in (visible, hidden, closed))
    assert isValid(retained)
    assert qapp is QApplication.instance()
    retained.deleteLater()


def test_cleanup_refuses_to_destroy_an_active_child_qthread(
    qapp: QApplication,
) -> None:
    started, release = Event(), Event()

    class HeldThread(QThread):
        def run(self) -> None:
            started.set()
            release.wait(10)

    preexisting = tuple(qapp.topLevelWidgets())
    owner = QWidget()
    worker = HeldThread(owner)
    worker.start()
    assert started.wait(5), "Worker did not start"

    try:
        with pytest.raises(
            pytest.fail.Exception, match="running QThreads"
        ):
            _dispose_test_windows(qapp, preexisting)
        assert isValid(owner)
        assert worker.isRunning()
    finally:
        release.set()
        assert worker.wait(5000), "Worker did not stop"

    _dispose_test_windows(qapp, preexisting)
    assert not isValid(owner)
    assert qapp is QApplication.instance()


def test_cleanup_refuses_unparented_active_mainwindow_worker_reference(
    qapp: QApplication,
) -> None:
    from app.ui.task_runner import Worker

    started, release = Event(), Event()

    def blocked_job(*, progress) -> None:
        started.set()
        release.wait(10)

    class WorkerOwner(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self._worker = Worker(blocked_job)

    preexisting = tuple(qapp.topLevelWidgets())
    owner = WorkerOwner()
    worker = owner._worker
    worker.start()
    assert started.wait(5), "Worker did not start"

    try:
        with pytest.raises(pytest.fail.Exception, match="running QThreads"):
            _dispose_test_windows(qapp, preexisting)
        assert isValid(owner)
        assert worker.isRunning()
    finally:
        release.set()
        assert worker.wait(5000), "Worker did not stop"

    _dispose_test_windows(qapp, preexisting)
    assert not isValid(owner)


def test_delete_on_close_does_not_destroy_running_child_qthread(
    qapp: QApplication,
) -> None:
    started, release = Event(), Event()

    class HeldThread(QThread):
        def run(self) -> None:
            started.set()
            release.wait(10)

    preexisting = tuple(qapp.topLevelWidgets())
    owner = QWidget()
    owner.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    worker = HeldThread(owner)
    worker.start()
    assert started.wait(5), "Worker did not start"

    try:
        with pytest.raises(pytest.fail.Exception, match="running QThreads"):
            _dispose_test_windows(qapp, preexisting)
        assert isValid(owner), "close() destroyed an active QThread owner"
        assert owner.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        assert worker.isRunning()
    finally:
        release.set()
        assert worker.wait(5000), "Worker did not stop"

    _dispose_test_windows(qapp, preexisting)
    assert not isValid(owner)


def test_delete_on_close_preserves_closeevent_worker_shutdown(
    qapp: QApplication,
) -> None:
    from app.ui.task_runner import Worker

    started, release = Event(), Event()

    def blocked_job(*, progress) -> None:
        started.set()
        release.wait(10)

    class ClosingOwner(QWidget):
        def __init__(self) -> None:
            super().__init__()
            self._worker = Worker(blocked_job)
            self.delete_flag_during_close: bool | None = None
            self.shutdown_ok = False

        def closeEvent(self, event: QCloseEvent) -> None:
            self.delete_flag_during_close = self.testAttribute(
                Qt.WidgetAttribute.WA_DeleteOnClose
            )
            release.set()
            self.shutdown_ok = self._worker.wait(5000)
            super().closeEvent(event)

    preexisting = tuple(qapp.topLevelWidgets())
    owner = ClosingOwner()
    owner.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    worker = owner._worker
    worker.start()
    assert started.wait(5), "Worker did not start"
    try:
        _dispose_test_windows(qapp, preexisting)
        assert owner.shutdown_ok
        assert owner.delete_flag_during_close is False
        assert not isValid(owner)
        assert not worker.isRunning()
    finally:
        release.set()
        assert worker.wait(5000), "Worker did not stop"


def test_rejected_close_keeps_window_alive_and_retries_after_acceptance(
    qapp: QApplication,
) -> None:
    class RejectingWindow(QWidget):
        allow_close = False

        def closeEvent(self, event: QCloseEvent) -> None:
            if self.allow_close:
                event.accept()
            else:
                event.ignore()

    preexisting = tuple(qapp.topLevelWidgets())
    owner = RejectingWindow()
    owner.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    owner.show()

    with pytest.raises(pytest.fail.Exception, match="refused to close"):
        _dispose_test_windows(qapp, preexisting)
    assert isValid(owner)
    assert owner.isVisible(), "Ignored close event must not hide the window"
    assert owner.testAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    owner.allow_close = True
    _dispose_test_windows(qapp, preexisting)
    assert not isValid(owner)


def test_hidden_delete_on_close_window_is_destroyed(
    qapp: QApplication,
) -> None:
    preexisting = tuple(qapp.topLevelWidgets())
    hidden = QWidget()
    hidden.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
    assert not hidden.isVisible()
    _dispose_test_windows(qapp, preexisting)
    assert not isValid(hidden)


def test_repeated_mainwindow_teardown_prevents_widget_accumulation(
    qapp: QApplication,
) -> None:
    preexisting = tuple(qapp.topLevelWidgets())
    baseline = len(QApplication.allWidgets())

    for _ in range(6):
        window = MainWindow()
        window.close()
        _dispose_test_windows(qapp, preexisting)
        assert not isValid(window)
        assert len(QApplication.allWidgets()) <= baseline + 10
