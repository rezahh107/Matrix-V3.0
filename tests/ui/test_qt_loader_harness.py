from __future__ import annotations

import pytest
from PySide6.QtCore import QCoreApplication, QThread, Signal

from tests.ui.qt_loader_harness import (
    wait_for_loader_failure,
    wait_for_loader_success,
)


class _ImmediateSuccessLoader(QThread):
    loaded: Signal = Signal(object)
    failed: Signal = Signal(str)

    def __init__(self, payload: object) -> None:
        super().__init__()
        self._payload = payload

    def run(self) -> None:
        self.loaded.emit(self._payload)


class _ImmediateFailureLoader(QThread):
    loaded: Signal = Signal(object)
    failed: Signal = Signal(str)

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def run(self) -> None:
        self.failed.emit(self._message)


class _DelayedLoader(QThread):
    loaded: Signal = Signal(object)
    failed: Signal = Signal(str)

    def run(self) -> None:
        QThread.msleep(50)


def test_harness_handles_repeated_immediate_success(
    qtbot: pytest.QtBot, qapp: QCoreApplication
) -> None:
    for iteration in range(50):
        loader = _ImmediateSuccessLoader(iteration)
        loader.setParent(qapp)

        payload = wait_for_loader_success(qtbot, loader, timeout_ms=1000)

        assert payload == iteration
        assert not loader.isRunning()


def test_harness_handles_repeated_immediate_failure(
    qtbot: pytest.QtBot, qapp: QCoreApplication
) -> None:
    for iteration in range(50):
        message = f"expected failure {iteration}"
        loader = _ImmediateFailureLoader(message)
        loader.setParent(qapp)

        error = wait_for_loader_failure(qtbot, loader, timeout_ms=1000)

        assert error == message
        assert not loader.isRunning()


def test_harness_timeout_reports_state_and_cleans_up(
    qtbot: pytest.QtBot, qapp: QCoreApplication
) -> None:
    loader = _DelayedLoader()
    loader.setParent(qapp)

    with pytest.raises(
        pytest.fail.Exception,
        match=r"loaded_count=0, failed_count=0, finished_count=0",
    ):
        wait_for_loader_success(qtbot, loader, timeout_ms=1)

    assert not loader.isRunning()
