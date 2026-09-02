from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtTest import QSignalSpy


def _last_signal_payload(spy: QSignalSpy) -> object | None:
    count = spy.count()
    if count == 0:
        return None

    arguments = spy.at(count - 1)
    if not arguments:
        return None
    return arguments[0]


def _wait_for_finish(
    _qtbot: Any, loader: QThread, timeout_ms: int
) -> tuple[bool | None, object | None]:
    """Wait for loader completion without depending on a future signal emission.

    Returns (success_flag, payload). success_flag is True for loaded, False for
    failed, and None if finished without emitting either.
    """

    app = QCoreApplication.instance()
    if app is None:
        pytest.fail("No active QCoreApplication for loader wait")

    success: bool | None = None
    payload: object | None = None
    timeout_diagnostic: str | None = None
    cleanup_error: str | None = None

    loaded_spy = QSignalSpy(loader.loaded)
    failed_spy = QSignalSpy(loader.failed)
    finished_spy = QSignalSpy(loader.finished)

    loader.start()

    try:
        finished_in_time = loader.wait(timeout_ms)
        app.processEvents()

        loaded_count = loaded_spy.count()
        failed_count = failed_spy.count()
        finished_count = finished_spy.count()

        if not finished_in_time:
            timeout_diagnostic = (
                f"Loader did not finish within {timeout_ms} ms; "
                f"loaded_count={loaded_count}, failed_count={failed_count}, "
                f"finished_count={finished_count}, is_running={loader.isRunning()}, "
                f"is_finished={loader.isFinished()}"
            )
        elif loaded_count > 0:
            success, payload = True, _last_signal_payload(loaded_spy)
        elif failed_count > 0:
            success, payload = False, _last_signal_payload(failed_spy)
        else:
            success, payload = None, None
    finally:
        if loader.isRunning():
            loader.requestInterruption()
            loader.quit()
            loader.wait(timeout_ms + 1000)

        if loader.isRunning():
            cleanup_error = "Loader thread did not terminate after wait"

        app.processEvents()

    if cleanup_error is not None:
        pytest.fail(cleanup_error)
    if timeout_diagnostic is not None:
        pytest.fail(timeout_diagnostic)

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
