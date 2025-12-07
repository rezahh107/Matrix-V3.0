from __future__ import annotations

import contextlib
from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication, QThread
from PySide6.QtTest import QSignalSpy


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

    success: bool | None = None
    payload: object | None = None

    loaded_spy = QSignalSpy(loader.loaded)
    failed_spy = QSignalSpy(loader.failed)
    finished_spy = QSignalSpy(loader.finished)

    loader.start()

    try:
        if not finished_spy.wait(timeout_ms):
            pytest.fail(
                f"Loader did not finish within {timeout_ms} ms; "
                f"loaded_count={len(loaded_spy)}, failed_count={len(failed_spy)}"
            )

        if loaded_spy:
            success, payload = True, loaded_spy[-1][0]
        elif failed_spy:
            success, payload = False, failed_spy[-1][0]
        else:
            success, payload = None, None
    finally:
        if loader.isRunning():
            loader.quit()
            loader.wait(timeout_ms + 1000)

        if loader.isRunning():
            pytest.fail("Loader thread did not terminate after wait")

        with contextlib.suppress(Exception):
            loader.deleteLater()
        qtbot.wait(10)

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
