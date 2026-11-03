from __future__ import annotations

import pytest

from app.ui.dialogs.unknown_data_dialog import summarize_unknowns_report


def test_unknowns_report_summary_limits_samples() -> None:
    report = {
        "issues": [
            {
                "entity_type": "student",
                "row_index": 3,
                "column": "کدرشته",
                "raw_value": "x",
                "error_code": "DATA_INVALID",
            },
            {
                "entity_type": "pool",
                "row_index": 5,
                "column": "جنسیت",
                "raw_value": None,
                "error_code": "DATA_MISSING",
            },
        ]
    }
    summary = summarize_unknowns_report(report, sample_limit=1)
    assert summary.total == 2
    assert len(summary.samples) == 1
    assert summary.samples[0].row_index == 3
    assert summary.by_entity_type["student"] == 1


def test_blocking_preflight_worker_does_not_report_completed_allocation(
    qapp, monkeypatch, tmp_path
) -> None:
    """Worker completion is not successful allocation after a blocking preflight."""
    import time

    from PySide6.QtWidgets import QMessageBox

    from app.ui import main_window_base
    from app.ui.main_window import MainWindow

    notices = []
    monkeypatch.setattr(
        main_window_base.cli,
        "main",
        lambda _argv, **_kwargs: 3,
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, _title, message: notices.append(str(message))),
    )
    window = MainWindow()
    proceeded = []
    try:
        window._run_unknowns_preflight(
            ["preflight-unknowns"],
            overrides={},
            report_path=tmp_path / "unknowns.json",
            on_proceed=lambda: proceeded.append(True),
        )
        worker = window._worker
        assert worker is not None
        deadline = time.monotonic() + 10
        while window._worker is not None and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        assert window._worker is None
        assert worker.wait(5000)
        assert notices
        assert not proceeded
        assert window._operation_state == "failed"
        assert window._btn_allocate.isEnabled()
    finally:
        window.close()
        qapp.processEvents()

@pytest.mark.parametrize(
    ("exit_code", "report", "approve", "expected_state", "allocation_started"),
    [
        (0, None, False, "completed", True),
        (3, None, False, "failed", False),
        (19, None, False, "failed", False),
        (None, None, False, "failed", False),
        (2, None, False, "failed", False),
        (2, "{not valid JSON", False, "failed", False),
        (2, '{"issues":[{"entity_type":"student"}]}', False, "failed", False),
        (2, '{"issues":[{"entity_type":"student"}],"summary":{"total":0}}', False, "failed", False),
        (2, '{"issues":[{"entity_type":"student"}],"summary":{}}', False, "failed", False),
        (2, '{"issues":[{"entity_type":"student"}],"summary":{"total":"1"}}', False, "failed", False),
        (2, '{"issues":[{"code":"DATA_INVALID","entity_type":"student"}],"summary":{"total":1,"by_entity_type":{"student":1},"by_code":{"DATA_INVALID":1}}}', False, "cancelled", False),
        (2, '{"issues":[{"code":"DATA_INVALID","entity_type":"student"}],"summary":{"total":1,"by_entity_type":{"student":1},"by_code":{"DATA_INVALID":1}}}', True, "completed", True),
        (2, '{"issues":[{"code":"DATA_INVALID","entity_type":"student"}],"summary":{"total":1,"by_entity_type":{"student":2},"by_code":{"DATA_INVALID":1}}}', False, "failed", False),
        (2, '{"issues":[{"code":"DATA_INVALID","entity_type":"student"}],"summary":{"total":1,"by_entity_type":{"student":1},"by_code":{"DATA_INVALID":"bad"}}}', False, "failed", False),
    ],
)
def test_preflight_terminal_status_and_allocation_worker_gate(
    qapp, monkeypatch, tmp_path, exit_code, report, approve, expected_state, allocation_started
) -> None:
    """Actual Qt preflight Worker; only clean/approved cases can launch an allocation Worker."""
    import time

    from PySide6.QtWidgets import QDialog, QMessageBox

    from app.ui import main_window_base
    from app.ui.main_window import MainWindow

    report_path = tmp_path / "unknowns.json"
    if report is not None:
        report_path.write_text(report, encoding="utf-8")

    monkeypatch.setattr(main_window_base.cli, "main", lambda *_args, **_kwargs: exit_code)
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *_args: None))

    class FakeDecisionDialog:
        def __init__(self, *_args, **_kwargs):
            self.should_proceed = approve

        def setModal(self, _modal):  # noqa: N802 - Qt API
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted if approve else QDialog.DialogCode.Rejected

    monkeypatch.setattr(main_window_base, "UnknownDataDialog", FakeDecisionDialog)

    window = MainWindow()
    launched = []
    workers = []
    original_launch = window._launch_worker

    def tracked_launch(func, action, **kwargs):
        launched.append(action)
        worker = original_launch(func, action, **kwargs)
        workers.append(worker)
        return worker

    window._launch_worker = tracked_launch
    try:
        window._run_unknowns_preflight(
            ["preflight-unknowns"],
            overrides={},
            report_path=report_path,
            on_proceed=lambda: window._launch_worker(
                lambda *, progress: None, "allocation-mock"
            ),
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            qapp.processEvents()
            if window._worker is None and window._operation_state == expected_state:
                break
            time.sleep(0.01)
        assert window._worker is None
        assert window._operation_state == expected_state
        assert ("allocation-mock" in launched) is allocation_started
        assert window._btn_allocate.isEnabled()
        assert window._progress.value() in (0, -1, 100)  # settled, not indeterminate
        assert window._progress.maximum() == 100
        for worker in workers:
            assert worker.wait(5000)
    finally:
        window.close()
        qapp.processEvents()


def test_preflight_summarizer_exception_is_failed_not_completed(
    qapp, monkeypatch, tmp_path
) -> None:
    """A callback exception must never be caught as a successful Worker completion."""
    import time

    from PySide6.QtWidgets import QMessageBox

    from app.ui import main_window_base
    from app.ui.main_window import MainWindow

    report_path = tmp_path / "unknowns.json"
    report_path.write_text(
        '{"issues":[{"code":"BAD","entity_type":"student"}],'
        '"summary":{"total":1,"by_entity_type":{"student":1},"by_code":{"BAD":1}}}',
        encoding="utf-8",
    )
    monkeypatch.setattr(main_window_base.cli, "main", lambda *_a, **_k: 2)
    monkeypatch.setattr(
        main_window_base,
        "summarize_unknowns_report",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("malformed synthetic summary")),
    )
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *_a: None))
    window = MainWindow()
    started = []
    try:
        window._run_unknowns_preflight(
            ["preflight-unknowns"], overrides={}, report_path=report_path,
            on_proceed=lambda: started.append(True),
        )
        deadline = time.monotonic() + 10
        while window._worker is not None and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.01)
        assert window._worker is None
        assert window._operation_state == "failed"
        assert not started
        assert window._progress.maximum() == 100
    finally:
        window.close()
        qapp.processEvents()
