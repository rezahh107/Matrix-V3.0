from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QThread
from PySide6.QtTest import QSignalSpy

from .conftest import waitSignal


def _wait_for_finish(qtbot: Any, loader: QThread, timeout_ms: int) -> tuple[QSignalSpy, QSignalSpy]:
    loaded_spy = QSignalSpy(loader.loaded)
    failed_spy = QSignalSpy(loader.failed)

    loader.start()

    try:
        waitSignal(loader.finished, timeout=timeout_ms)
    except Exception:
        if loader.isRunning():
            loader.requestInterruption()
            loader.quit()
            loader.wait(500)
        raise
    finally:
        loader.wait(1000)
        loader.deleteLater()
        qtbot.wait(10)

    return loaded_spy, failed_spy


def wait_for_loader_success(qtbot: Any, loader: QThread, timeout_ms: int = 5000) -> Any:
    loaded_spy, failed_spy = _wait_for_finish(qtbot, loader, timeout_ms)

    if failed_spy:
        pytest.fail(f"Loader failed unexpectedly: {failed_spy[0][0]}")

    assert loaded_spy, "Loader did not emit loaded signal"
    return loaded_spy[0][0]


def wait_for_loader_failure(qtbot: Any, loader: QThread, timeout_ms: int = 5000) -> str:
    loaded_spy, failed_spy = _wait_for_finish(qtbot, loader, timeout_ms)

    if loaded_spy:
        pytest.fail("Loader emitted loaded signal but failure was expected")

    assert failed_spy, "Loader did not emit failure signal"
    return str(failed_spy[0][0])
