"""Native QThread lifetime regression for PR #39 (synthetic data only).

The custom Worker.finished(bool, object) is emitted while run() remains active.
The independent safety_refs list deliberately prevents a use-after-free crash
if the old MainWindow code drops _worker before the native thread stops.

Run on a disposable Windows/PySide6 checkout, pinned to the target commit plus
this unmerged local patch. This module is expected to fail on original PR #39.
"""

from __future__ import annotations

import threading
import time

import pytest

pytest.importorskip("PySide6.QtWidgets")

from app.ui import main_window_base  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.task_runner import WorkerCancelled  # noqa: E402


def _pump(qapp, predicate, *, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.01)
    qapp.processEvents()
    return predicate()


def _result_delivered_or_old_owner_released(window: MainWindow) -> bool:
    # On original PR #39 the test MUST reach the old early release and fail its
    # ownership assertion; on repaired source the result is held until join.
    return (
        getattr(window, "_pending_worker_result", None) is not None
        or window._worker is None
    )


@pytest.mark.parametrize("outcome", ["success", "failure", "cancelled"])
def test_custom_result_cannot_release_native_worker(
    qapp, monkeypatch, outcome: str
) -> None:
    """The negative control rejects original ownership release for every result."""
    window = MainWindow()
    released = threading.Event()
    result_emitted = threading.Event()
    started = threading.Event()
    safety_refs = []
    hooks = []
    real_worker = main_window_base.Worker
    monkeypatch.setattr(window, "_show_async_message", lambda *_a: None)

    class HeldAfterResult(real_worker):
        def start(self) -> None:
            safety_refs.append(self)  # strong ref BEFORE native start
            super().start()

        def run(self) -> None:
            super().run()  # emits CUSTOM finished(bool, object), not native finish
            result_emitted.set()
            if not released.wait(20):
                raise TimeoutError("synthetic post-result hold expired")

    monkeypatch.setattr(main_window_base, "Worker", HeldAfterResult)

    def task(*, progress) -> None:
        started.set()
        if outcome == "failure":
            raise RuntimeError("synthetic failure")
        if outcome == "cancelled":
            raise WorkerCancelled("synthetic cancellation")

    try:
        worker = window._launch_worker(
            task, "synthetic native-thread lifetime", on_success=lambda: hooks.append(1)
        )
        assert safety_refs == [worker]
        assert started.wait(5)
        assert result_emitted.wait(5)
        assert worker.isRunning()
        assert not worker.wait(0)
        assert _pump(qapp, lambda: _result_delivered_or_old_owner_released(window))

        assert window._worker is worker, "EARLY_OWNERSHIP_RELEASE: result != native termination"
        assert not window._btn_allocate.isEnabled()
        assert window._operation_state == "running"
        assert not hooks
        # A programmatic attempt cannot replace the owned Worker.
        with pytest.raises(RuntimeError, match="previous Worker"):
            window._launch_worker(lambda *, progress: None, "overlap prohibited")
        assert window._worker is worker
        assert not worker.wait(0)

        released.set()
        assert _pump(qapp, lambda: window._worker is None)
        assert worker.wait(0), "ownership released without a successful native join"
        assert window._operation_state == {
            "success": "completed",
            "failure": "failed",
            "cancelled": "cancelled",
        }[outcome]
        assert hooks == ([1] if outcome == "success" else [])
        assert window._btn_allocate.isEnabled()
    finally:
        released.set()
        for worker in safety_refs:
            assert worker.wait(10000), "SAFETY: native QThread did not join"
        window.close()
        qapp.processEvents()


def test_after_start_handoff_failure_keeps_both_references_until_join(
    qapp, monkeypatch, tmp_path, caplog
) -> None:
    """After-start exception, late result, no false success or progress, then retry."""
    window = MainWindow()
    released = threading.Event()
    result_emitted = threading.Event()
    safety_refs = []  # includes the preflight Worker as well
    allocation_refs = []
    success_hooks = []
    private_marker = "SYNTHETIC_DO_NOT_LOG"
    real_worker = main_window_base.Worker
    monkeypatch.setattr(main_window_base.cli, "main", lambda *_a, **_kw: 0)
    monkeypatch.setattr(window, "_show_async_message", lambda *_a: None)

    class AfterStartExceptionWorker(real_worker):
        def start(self) -> None:
            safety_refs.append(self)  # independent reference BEFORE native start
            if window._current_action == "synthetic-allocation":
                allocation_refs.append(self)
                self._hold_for_diagnostic = True
                super().start()
                raise RuntimeError(private_marker)
            self._hold_for_diagnostic = False
            super().start()

        def run(self) -> None:
            super().run()
            if self._hold_for_diagnostic:
                result_emitted.set()
                if not released.wait(20):
                    raise TimeoutError("synthetic post-result hold expired")

    monkeypatch.setattr(main_window_base, "Worker", AfterStartExceptionWorker)
    try:
        window._run_unknowns_preflight(
            ["preflight-unknowns"],
            overrides={},
            report_path=tmp_path / "synthetic-report.json",
            on_proceed=lambda: window._launch_worker(
                lambda *, progress: None,
                "synthetic-allocation",
                on_success=lambda: success_hooks.append("wrong"),
            ),
        )
        assert _pump(qapp, lambda: len(allocation_refs) == 1)
        worker = allocation_refs[0]
        assert result_emitted.wait(5)
        assert _pump(qapp, lambda: _result_delivered_or_old_owner_released(window))
        assert worker.isRunning() and not worker.wait(0)
        assert window._worker is worker, "EARLY_OWNERSHIP_RELEASE after handoff failure"
        assert window._handoff_failed_worker is worker
        assert not window._btn_allocate.isEnabled()
        assert window._operation_state == "failed"
        worker.progress.emit(99, "synthetic late progress")
        qapp.processEvents()
        assert window._operation_state == "failed"
        assert not success_hooks
        assert private_marker not in caplog.text
        assert private_marker not in window._log.toPlainText()

        released.set()
        assert _pump(qapp, lambda: window._worker is None)
        assert worker.wait(0)
        assert window._handoff_failed_worker is None
        assert window._operation_state == "failed"
        assert window._btn_allocate.isEnabled()
        assert not success_hooks
        # Recovery cannot be blocked by stale state after the true join.
        retry = window._launch_worker(
            lambda *, progress: None,
            "synthetic-retry",
            on_success=lambda: success_hooks.append("retry"),
        )
        assert retry in safety_refs
        assert _pump(qapp, lambda: window._worker is None)
        assert retry.wait(0)
        assert success_hooks == ["retry"]
    finally:
        released.set()
        for worker in safety_refs:
            assert worker.wait(10000), "SAFETY: native QThread did not join"
        window.close()
        qapp.processEvents()


def test_before_start_failure_reenables_controls(qapp, monkeypatch, tmp_path) -> None:
    """Failure before native start requires no poll and permits a clean retry."""
    window = MainWindow()
    safety_refs = []
    before_start_refs = []
    real_worker = main_window_base.Worker
    original_start = real_worker.start
    monkeypatch.setattr(main_window_base.cli, "main", lambda *_a, **_kw: 0)
    monkeypatch.setattr(window, "_show_async_message", lambda *_a: None)

    def fail_before_start(worker) -> None:
        safety_refs.append(worker)  # protects the preflight worker too
        if window._current_action == "synthetic-allocation":
            before_start_refs.append(worker)
            raise RuntimeError("synthetic failure before native start")
        original_start(worker)

    monkeypatch.setattr(real_worker, "start", fail_before_start)
    try:
        window._run_unknowns_preflight(
            ["preflight-unknowns"],
            overrides={},
            report_path=tmp_path / "synthetic-report.json",
            on_proceed=lambda: window._launch_worker(
                lambda *, progress: None, "synthetic-allocation"
            ),
        )
        assert _pump(qapp, lambda: window._worker is None)
        assert len(before_start_refs) == 1
        assert not before_start_refs[0].isRunning()
        assert window._operation_state == "failed"
        assert window._btn_allocate.isEnabled()
        assert not window._is_busy_cursor
        retry = window._launch_worker(lambda *, progress: None, "synthetic-recovery")
        assert retry in safety_refs
        assert _pump(qapp, lambda: window._worker is None)
        assert retry.wait(0)
        assert window._operation_state == "completed"
    finally:
        for worker in safety_refs:
            assert worker.wait(10000)
        window.close()
        qapp.processEvents()


def test_close_refuses_noncooperative_post_result_thread(qapp, monkeypatch) -> None:
    """A close during post-result run() must neither orphan nor block indefinitely."""
    window = MainWindow()
    released = threading.Event()
    result_emitted = threading.Event()
    safety_refs = []
    real_worker = main_window_base.Worker

    class HeldAfterResult(real_worker):
        def start(self) -> None:
            safety_refs.append(self)
            super().start()

        def run(self) -> None:
            super().run()
            result_emitted.set()
            if not released.wait(20):
                raise TimeoutError("synthetic post-result hold expired")

    monkeypatch.setattr(main_window_base, "Worker", HeldAfterResult)
    window.show()
    try:
        worker = window._launch_worker(lambda *, progress: None, "synthetic-close")
        assert result_emitted.wait(5)
        assert _pump(qapp, lambda: _result_delivered_or_old_owner_released(window))
        assert window._worker is worker
        assert worker.isRunning() and not worker.wait(0)
        started_at = time.monotonic()
        assert not window.close()
        assert time.monotonic() - started_at < 5  # bounded existing 3-second wait
        assert window._worker is worker
        assert not window._is_closing
        assert worker.isRunning()
        released.set()
        assert _pump(qapp, lambda: window._worker is None)
        assert worker.wait(0)
        assert window.close()
    finally:
        released.set()
        for worker in safety_refs:
            assert worker.wait(10000), "SAFETY: native QThread did not join"
        window.close()
        qapp.processEvents()


def test_request_cancel_waits_for_native_termination(qapp, monkeypatch) -> None:
    """Exercise request_cancel -> WorkerCancelled -> queued result -> native join."""
    window = MainWindow()
    permit_progress = threading.Event()
    task_started = threading.Event()
    custom_emitted = threading.Event()
    released = threading.Event()
    safety_refs = []
    real_worker = main_window_base.Worker

    class CancelledButNativeHeld(real_worker):
        def start(self) -> None:
            safety_refs.append(self)
            super().start()

        def run(self) -> None:
            super().run()
            custom_emitted.set()
            if not released.wait(20):
                raise TimeoutError("synthetic post-cancel hold expired")

    monkeypatch.setattr(main_window_base, "Worker", CancelledButNativeHeld)

    def cooperative_task(*, progress) -> None:
        task_started.set()
        if not permit_progress.wait(10):
            raise TimeoutError("synthetic cancel gate expired")
        progress(15, "synthetic progress after cancellation")

    try:
        worker = window._launch_worker(cooperative_task, "synthetic cooperative cancellation")
        assert task_started.wait(5)
        worker.request_cancel()
        permit_progress.set()
        assert custom_emitted.wait(5)
        assert _pump(qapp, lambda: _result_delivered_or_old_owner_released(window))
        assert worker.isRunning() and not worker.wait(0)
        assert window._worker is worker
        assert not window._btn_allocate.isEnabled()
        released.set()
        assert _pump(qapp, lambda: window._worker is None)
        assert worker.wait(0)
        assert window._operation_state == "cancelled"
        assert window._btn_allocate.isEnabled()
    finally:
        permit_progress.set()
        released.set()
        for worker in safety_refs:
            assert worker.wait(10000), "SAFETY: cancelled QThread did not join"
        window.close()
        qapp.processEvents()


@pytest.mark.parametrize(
    ("qt_running", "native_joined", "close_allowed"),
    [
        (True, False, False),
        (False, False, False),
        (False, True, True),
    ],
    ids=[
        "running-unjoined-refused",
        "not-running-still-unjoined-refused",
        "joined-close-allowed",
    ],
)
def test_close_guard_uses_native_join_not_is_running(
    qapp, qt_running: bool, native_joined: bool, close_allowed: bool
) -> None:
    """Deterministically discriminate Qt's isRunning()/wait(0) cleanup gap.

    This *synthetic-state* control complements, but cannot replace, the native
    QThread tests above. In particular the second case MUST fail with the
    original closeEvent implementation even if its other Qt tests pass.
    """
    class TerminationBoundaryStub:
        def __init__(self) -> None:
            self.joined = native_joined
            self.calls: list[object] = []
            self.cancelled = False

        def isRunning(self) -> bool:  # noqa: N802 - Qt API shape
            self.calls.append("isRunning")
            return qt_running

        def wait(self, ms: int) -> bool:
            self.calls.append(("wait", ms))
            return self.joined

        def request_cancel(self) -> None:
            self.calls.append("request_cancel")
            self.cancelled = True

    window = MainWindow()
    worker = TerminationBoundaryStub()
    stop_event = threading.Event()
    window.show()
    window._worker = worker  # type: ignore[assignment] -- intentional boundary injection
    window._worker_stop_event = stop_event
    try:
        assert window.close() is close_allowed, "CLOSE_GUARD_BYPASS: close accepted before join"
        assert worker.calls[0] == ("wait", 0), "closeEvent must consult native join"
        if close_allowed:
            assert worker.calls == [("wait", 0)]
            assert not stop_event.is_set()
            assert not worker.cancelled
        else:
            assert window._worker is worker
            assert worker.calls == [("wait", 0), "request_cancel", ("wait", 3000)]
            assert stop_event.is_set()
            assert worker.cancelled
            assert not window._is_closing
    finally:
        # Always allow deterministic cleanup without a real background thread.
        worker.joined = True
        window.close()
        qapp.processEvents()
