"""Regression checks for per-test Qt window ownership and teardown."""

from __future__ import annotations

from threading import Event

import pytest
from PySide6.QtCore import QThread
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
