import sqlite3

import pandas as pd
import pytest

try:
    from PySide6.QtWidgets import QApplication, QMessageBox
except ImportError as exc:  # pragma: no cover - محیط فاقد وابستگی Qt
    pytest.skip(f"PySide6 unavailable: {exc}", allow_module_level=True)

from app.infra.local_database import LocalDatabase, RunMetricRow, RunRecord
from app.infra.year_database_manager import YearDatabaseManager
from app.ui import main_window_base
from app.ui.history_dialog import HistoryDialog
from app.ui.main_window import MainWindow


@pytest.fixture()
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _insert_run_with_snapshots(db: LocalDatabase) -> None:
    record = RunRecord(
        run_uuid="ui-run",
        started_at=pd.Timestamp.utcnow().to_pydatetime(),
        finished_at=pd.Timestamp.utcnow().to_pydatetime(),
        policy_version="1.0.3",
        ssot_version="1.0.2",
        entrypoint="allocate",
        cli_args=None,
        db_path=None,
        input_files_json="{}",
        input_hashes_json="{}",
        total_students=2,
        total_allocated=1,
        total_unallocated=1,
        history_metrics_json=None,
        qa_summary_json=None,
        status="success",
        message=None,
    )
    run_id = db.insert_run(record)

    trace_df = pd.DataFrame({"student_id": [1], "step": ["type"], "candidates": [3]})
    summary_df = pd.DataFrame({"allocation_channel": ["SCHOOL"], "students_total": [2]})
    db.insert_trace_snapshot(
        run_id=run_id, trace_df=trace_df, summary_df=summary_df, history_info_df=None
    )

    qa_summary_df = pd.DataFrame(
        [{"rule_id": "QA_RULE_ALLOC_01", "status": "FAIL", "violations_count": 1}]
    )
    qa_details_df = pd.DataFrame(
        [
            {
                "rule_id": "QA_RULE_ALLOC_01",
                "level": "error",
                "message": "over capacity",
                "student_id": 5,
            }
        ]
    )
    db.insert_qa_snapshot(run_id=run_id, qa_summary_df=qa_summary_df, qa_details_df=qa_details_df)

    db.insert_run_metrics(
        [RunMetricRow(run_id=run_id, metric_key="SCHOOL.students_total", metric_value=2.0)]
    )


def test_history_dialog_loads_snapshots(qapp: QApplication, tmp_path) -> None:
    db = LocalDatabase(tmp_path / "ui.db")
    db.initialize()
    _insert_run_with_snapshots(db)

    dialog = HistoryDialog(db)
    dialog._on_run_selected(dialog._run_list.currentRow())

    assert dialog.trace_model.rowCount() == 1
    assert dialog.qa_summary_model.rowCount() == 1
    assert dialog.qa_details_model.rowCount() == 1
    assert dialog.metrics_model.rowCount() == 1


def _isolated_main_window(monkeypatch: pytest.MonkeyPatch, tmp_path) -> MainWindow:
    monkeypatch.setattr(
        main_window_base,
        "YearDatabaseManager",
        lambda _root: YearDatabaseManager(tmp_path / "years"),
    )
    return MainWindow()


def test_operator_run_history_empty_state(
    qapp: QApplication, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _isolated_main_window(monkeypatch, tmp_path)
    try:
        action = window._support_toolbar_actions["run_history"]
        assert action.objectName() == "actionRunHistory"
        assert window._support_toolbar_actions["history"].objectName() == "actionHistoryMetrics"
        window.show()
        action.trigger()
        dialog = window._run_history_dialog
        assert dialog is not None and dialog.isVisible()
        assert dialog._run_list.count() == 0
        assert dialog.trace_model.rowCount() == 0
        assert dialog.qa_summary_model.rowCount() == 0
        assert dialog.metrics_model.rowCount() == 0
        dialog.close()
    finally:
        window.close()
        qapp.processEvents()


def test_operator_run_history_read_failure_preserves_prior_records(
    qapp: QApplication, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = _isolated_main_window(monkeypatch, tmp_path)
    db = LocalDatabase(tmp_path / "read-failure.db")
    db.initialize()
    _insert_run_with_snapshots(db)
    window._local_db = db
    notices: list[tuple[str, str]] = []

    def fail_fetch_runs() -> list[object]:
        raise sqlite3.OperationalError("synthetic retrieval failure")

    monkeypatch.setattr(db, "fetch_runs", fail_fetch_runs)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, message: notices.append((title, message))),
    )
    try:
        window.show()
        window._support_toolbar_actions["run_history"].trigger()
        assert len(notices) == 1
        assert notices[0][0] == window._t("history.load_failed.title", "Run history unavailable")
        assert window._run_history_dialog is None

        restored = LocalDatabase(db.path)
        runs = restored.fetch_runs()
        assert len(runs) == 1 and runs[0]["run_uuid"] == "ui-run"
        saved_trace, _, _ = restored.fetch_trace_snapshot(int(runs[0]["id"]))
        assert saved_trace is not None
        assert saved_trace["student_id"].tolist() == [1]
        saved_qa, saved_details, _ = restored.fetch_qa_snapshot(int(runs[0]["id"]))
        assert saved_qa is not None and len(saved_qa) == 1
        assert saved_details is not None and len(saved_details) == 1
    finally:
        window.close()
        qapp.processEvents()
