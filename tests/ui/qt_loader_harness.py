from __future__ import annotations

import contextlib
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication, QEventLoop, QThread, QTimer


def _wait_for_finish(
    qtbot: Any, loader: QThread, timeout_ms: int
) -> tuple[bool | None, object | None]:
    """Wait for loader completion using the Qt event loop only.

    Returns (success_flag, payload). success_flag is True for loaded, False for
    failed, and None if finished without emitting either.
    """

    app = QCoreApplication.instance()
    if app is None:
        pytest.fail("No active QCoreApplication for loader wait")

    loop = QEventLoop()
    timed_out = False
    success: bool | None = None
    payload: object | None = None

    def _on_loaded(result: object) -> None:
        nonlocal success, payload
        success, payload = True, result
        if loop.isRunning():
            loop.quit()

    def _on_failed(message: object) -> None:
        nonlocal success, payload
        success, payload = False, message
        if loop.isRunning():
            loop.quit()

    def _on_finished() -> None:
        if success is None and loop.isRunning():
            loop.quit()

    def _on_timeout() -> None:
        nonlocal timed_out
        timed_out = True
        if loop.isRunning():
            loop.quit()

    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(_on_timeout)

    loader.loaded.connect(_on_loaded)
    loader.failed.connect(_on_failed)
    loader.finished.connect(_on_finished)

    loader.start()
    timer.start(timeout_ms)

    try:
        loop.exec()
    finally:
        timer.stop()
        with contextlib.suppress(Exception):
            loader.loaded.disconnect(_on_loaded)
        with contextlib.suppress(Exception):
            loader.failed.disconnect(_on_failed)
        with contextlib.suppress(Exception):
            loader.finished.disconnect(_on_finished)
        with contextlib.suppress(Exception):
            timer.timeout.disconnect(_on_timeout)

        if loader.isRunning():
            loader.quit()
            loader.wait(timeout_ms + 1000)

        if loader.isRunning():
            pytest.fail("Loader thread did not terminate after wait")

        loader.deleteLater()
        qtbot.wait(10)

    if timed_out:
        pytest.fail(
            f"Timed out after {timeout_ms} ms waiting for loader signals; success={success}"
        )

    return success, payload


def wait_for_loader_success(qtbot: Any, loader: QThread, timeout_ms: int = 5000) -> Any:
    success, payload = _wait_for_finish(qtbot, loader, timeout_ms)

    if success is False:
        pytest.fail(f"Loader failed unexpectedly: {payload}")

    assert success is True, "Loader did not emit loaded signal"
    return payload


def wait_for_loader_failure(qtbot: Any, loader: QThread, timeout_ms: int = 5000) -> str:
    success, payload = _wait_for_finish(qtbot, loader, timeout_ms)

    if success is True:
        pytest.fail("Loader emitted loaded signal but failure was expected")

    assert success is False, "Loader did not emit failure signal"
    return str(payload)
