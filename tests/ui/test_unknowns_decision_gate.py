from __future__ import annotations

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
