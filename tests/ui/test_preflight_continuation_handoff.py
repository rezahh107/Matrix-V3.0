"""Regression: a successful unknowns preflight must hand off to allocation safely.

Uses the real MainWindow, real Qt Worker signals, and a synthetic CLI result.
No student workbooks or organizational Sabt profile are needed.
"""

from __future__ import annotations

import json
import time

import pytest

pytest.importorskip("PySide6.QtWidgets")

from PySide6.QtWidgets import QDialog  # noqa: E402

from app.ui import main_window_base  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402

_SYNTHETIC_PRIVATE_MARKER = "SYNTHETIC_SENSITIVE_CONTINUATION_DETAILS"


def _valid_report() -> dict[str, object]:
    return {
        "issues": [
            {
                "entity_type": "student",
                "code": "DATA_INVALID",
                "error_code": "DATA_INVALID",
                "row_index": 3,
            }
        ],
        "summary": {
            "total": 1,
            "by_entity_type": {"student": 1},
            "by_code": {"DATA_INVALID": 1},
        },
    }


def _wait_for_idle(qapp, window: MainWindow, *, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if window._worker is None:
            # Drain queued worker completion/state signals too.
            qapp.processEvents()
            if window._worker is None:
                return
        time.sleep(0.01)
    pytest.fail("Timed out waiting for the real Qt Worker to become idle")


@pytest.mark.parametrize("exit_code", [0, 2], ids=["clean", "approved-issues"])
def test_continuation_exception_is_failed_in_real_qt(
    qapp, monkeypatch, tmp_path, caplog, exit_code: int
) -> None:
    """Reproduce a continuation raising BEFORE an Allocation Worker exists."""
    report_path = tmp_path / "unknowns.json"
    if exit_code == 2:
        report_path.write_text(json.dumps(_valid_report()), encoding="utf-8")

    monkeypatch.setattr(main_window_base.cli, "main", lambda *_a, **_kw: exit_code)

    class ApprovedDecisionDialog:
        should_proceed = True

        def __init__(self, *_a, **_kw) -> None:
            pass

        def setModal(self, _modal: bool) -> None:  # noqa: N802 - actual Qt API
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window_base, "UnknownDataDialog", ApprovedDecisionDialog)
    shown: list[str] = []
    started: list[bool] = []
    window = MainWindow()
    monkeypatch.setattr(window, "_show_async_message", lambda _icon, _title, message: shown.append(str(message)))

    def fail_before_allocation() -> None:
        started.append(True)
        assert window._worker is None  # The original preflight Worker finished.
        raise RuntimeError(_SYNTHETIC_PRIVATE_MARKER)

    try:
        window._run_unknowns_preflight(
            ["preflight-unknowns"],
            overrides={},
            report_path=report_path,
            on_proceed=fail_before_allocation,
        )
        preflight_worker = window._worker
        assert preflight_worker is not None
        _wait_for_idle(qapp, window)
        assert preflight_worker.wait(5000)
        assert len(started) == 1
        assert window._operation_state == "failed"  # fails on unmodified 10407 HEAD
        assert window._status.text() == window._t("status.error", "خطا")
        assert window._progress.maximum() == 100
        assert window._progress.value() in (-1, 0)
        assert window._btn_allocate.isEnabled()
        assert shown  # operator-facing, nonblocking feedback
        assert all(_SYNTHETIC_PRIVATE_MARKER not in message for message in shown)
        assert _SYNTHETIC_PRIVATE_MARKER not in caplog.text
        assert _SYNTHETIC_PRIVATE_MARKER not in window._log.toPlainText()
    finally:
        window.close()
        qapp.processEvents()


@pytest.mark.parametrize("exit_code", [0, 2], ids=["clean", "approved-issues"])
def test_successful_continuation_starts_real_allocation_worker(
    qapp, monkeypatch, tmp_path, exit_code: int
) -> None:
    """Positive control: a handoff launches a second real Worker and completes."""
    report_path = tmp_path / "unknowns.json"
    if exit_code == 2:
        report_path.write_text(json.dumps(_valid_report()), encoding="utf-8")
    monkeypatch.setattr(main_window_base.cli, "main", lambda *_a, **_kw: exit_code)

    class ApprovedDecisionDialog:
        should_proceed = True

        def __init__(self, *_a, **_kw) -> None:
            pass

        def setModal(self, _modal: bool) -> None:  # noqa: N802 - actual Qt API
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window_base, "UnknownDataDialog", ApprovedDecisionDialog)
    window = MainWindow()
    started: list[str] = []
    workers = []
    actual_launch = window._launch_worker

    def observe_launch(func, action, **kwargs):
        started.append(str(action))
        worker = actual_launch(func, action, **kwargs)
        workers.append(worker)
        return worker

    monkeypatch.setattr(window, "_launch_worker", observe_launch)

    try:
        window._run_unknowns_preflight(
            ["preflight-unknowns"],
            overrides={},
            report_path=report_path,
            on_proceed=lambda: window._launch_worker(
                lambda *, progress: None, "synthetic-allocation-worker"
            ),
        )
        _wait_for_idle(qapp, window)
        assert "synthetic-allocation-worker" in started
        assert window._operation_state == "completed"
        assert window._btn_allocate.isEnabled()
        assert all(worker.wait(5000) for worker in workers)
    finally:
        window.close()
        qapp.processEvents()


@pytest.mark.parametrize("exit_code", [0, 2], ids=["clean", "approved-issues"])
def test_partial_allocation_worker_start_exception_releases_ui(
    qapp, monkeypatch, tmp_path, caplog, exit_code: int
) -> None:
    """Worker.start may raise after _launch_worker assigns ownership and marks UI busy."""
    report_path = tmp_path / "unknowns.json"
    if exit_code == 2:
        report_path.write_text(json.dumps(_valid_report()), encoding="utf-8")
    monkeypatch.setattr(main_window_base.cli, "main", lambda *_a, **_kw: exit_code)

    class ApprovedDecisionDialog:
        should_proceed = True

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def setModal(self, _modal: bool) -> None:  # noqa: N802 - Qt API
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window_base, "UnknownDataDialog", ApprovedDecisionDialog)
    window = MainWindow()
    feedback: list[str] = []
    monkeypatch.setattr(
        window, "_show_async_message", lambda _icon, _title, message: feedback.append(str(message))
    )
    worker_cls = main_window_base.Worker
    original_start = worker_cls.start
    attempted: list[object] = []

    def start_or_raise(worker) -> None:
        if window._current_action == "synthetic-allocation-worker":
            attempted.append(worker)
            # The Worker is already owned by MainWindow when start() is called.
            assert window._worker is worker
            raise RuntimeError(_SYNTHETIC_PRIVATE_MARKER)
        return original_start(worker)

    monkeypatch.setattr(worker_cls, "start", start_or_raise)

    try:
        window._run_unknowns_preflight(
            ["preflight-unknowns"],
            overrides={},
            report_path=report_path,
            on_proceed=lambda: window._launch_worker(
                lambda *, progress: None,
                "synthetic-allocation-worker",
                on_success=lambda: None,
            ),
        )
        preflight_worker = window._worker
        assert preflight_worker is not None
        _wait_for_idle(qapp, window)
        assert preflight_worker.wait(5000)
        assert len(attempted) == 1
        assert not attempted[0].isRunning()
        assert window._worker is None
        assert window._success_hook is None
        assert window._operation_state == "failed"
        assert window._status.text() == window._t("status.error", "خطا")
        assert window._btn_allocate.isEnabled()
        assert not window._is_busy_cursor
        assert window._progress.maximum() == 100
        assert window._progress.value() in (-1, 0)
        assert not window._progress.property("busy")
        assert feedback
        assert all(_SYNTHETIC_PRIVATE_MARKER not in message for message in feedback)
        assert _SYNTHETIC_PRIVATE_MARKER not in caplog.text
        log_text = window._log.toPlainText()
        assert _SYNTHETIC_PRIVATE_MARKER not in log_text
        assert log_text.rfind("❌") > log_text.rfind("✅")
        assert window._t("error.unknowns.continuation_failed", "ادامهٔ تخصیص پس از پیش‌بررسی با خطا مواجه شد. پیش از تلاش دوباره خروجی‌ها را بررسی کنید.") in log_text
        window._run_unknowns_preflight(
            ["preflight-unknowns"],
            overrides={},
            report_path=report_path,
            on_proceed=lambda: window._launch_worker(
                lambda *, progress: None, "recovery-allocation-worker"
            ),
        )
        _wait_for_idle(qapp, window)
        assert window._operation_state == "completed"
        assert window._worker is None
        assert window._btn_allocate.isEnabled()
    finally:
        window.close()
        qapp.processEvents()


def test_start_raises_after_launch_preserves_worker_and_blocks_false_success(
    qapp, monkeypatch, tmp_path, caplog
) -> None:
    """The handoff can fail after QThread.start has actually launched work."""
    import threading

    window = MainWindow()
    released = threading.Event()
    original_start = main_window_base.Worker.start
    attempted = []
    successful_hooks = []
    messages = []
    monkeypatch.setattr(main_window_base.cli, "main", lambda *_a, **_kw: 0)
    monkeypatch.setattr(
        window, "_show_async_message",
        lambda _icon, _title, message: messages.append(str(message)),
    )

    def start_then_raise(worker) -> None:
        original_start(worker)
        if window._current_action == "synthetic-allocation-worker":
            attempted.append(worker)
            raise RuntimeError(_SYNTHETIC_PRIVATE_MARKER)

    monkeypatch.setattr(main_window_base.Worker, "start", start_then_raise)
    try:
        window._run_unknowns_preflight(
            ["preflight-unknowns"],
            overrides={},
            report_path=tmp_path / "unknowns.json",
            on_proceed=lambda: window._launch_worker(
                lambda *, progress: released.wait(10),
                "synthetic-allocation-worker",
                on_success=lambda: successful_hooks.append(True),
            ),
        )
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not attempted:
            qapp.processEvents()
            time.sleep(0.01)
        assert len(attempted) == 1
        assert window._worker is attempted[0]
        assert window._handoff_failed_worker is attempted[0]
        assert not window._btn_allocate.isEnabled()
        assert window._operation_state == "failed"
        released.set()
        _wait_for_idle(qapp, window)
        assert attempted[0].wait(5000)
        assert window._handoff_failed_worker is None
        assert window._operation_state == "failed"
        assert window._btn_allocate.isEnabled()
        assert not successful_hooks
        assert messages
        assert _SYNTHETIC_PRIVATE_MARKER not in caplog.text
        assert _SYNTHETIC_PRIVATE_MARKER not in window._log.toPlainText()
        assert all(_SYNTHETIC_PRIVATE_MARKER not in m for m in messages)
    finally:
        released.set()
        if window._worker is not None:
            window._worker.wait(5000)
        window.close()
        qapp.processEvents()


def test_close_refuses_to_orphan_running_worker(qapp) -> None:
    """A non-cooperative QThread must outlive an ignored window-close request."""
    import threading

    window = MainWindow()
    released = threading.Event()
    started = threading.Event()
    worker = None
    window.show()
    try:
        def work(*, progress) -> None:
            started.set()
            released.wait(10)

        worker = window._launch_worker(work, "synthetic-blocking-worker")
        assert started.wait(5)
        qapp.processEvents()
        assert not window.close()
        assert window._worker is worker
        assert worker.isRunning()
        assert not window._is_closing
        released.set()
        _wait_for_idle(qapp, window)
        assert worker.wait(5000)
        assert window.close()
    finally:
        released.set()
        if worker is not None:
            worker.wait(5000)
        window.close()
        qapp.processEvents()
