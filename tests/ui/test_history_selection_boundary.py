"""PRI-FND-001: failed Qt run selections must not misattribute stored snapshots."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
except ImportError as exc:  # pragma: no cover - PySide6 provided on Windows UI runner
    pytest.skip(f"PySide6 unavailable: {exc}", allow_module_level=True)

from app.infra.errors import DatabaseOperationError
from app.infra.local_database import LocalDatabase, RunMetricRow, RunRecord
from app.infra.year_database_manager import YearDatabaseManager
from app.ui import main_window_base
from app.ui.history_dialog import DataFrameTableModel, HistoryDialog
from app.ui.main_window import MainWindow
from app.ui.texts import UiTranslator


@pytest.fixture()
def qapp() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def history_db(tmp_path: Path) -> LocalDatabase:
    db = LocalDatabase(tmp_path / "selection-history.sqlite")
    db.initialize()
    started = datetime(2026, 11, 8, tzinfo=UTC)
    for idx, tag in enumerate(("A", "B")):
        current = started + timedelta(seconds=idx)
        run_id = db.insert_run(
            RunRecord(
                run_uuid=f"synthetic-{tag}",
                started_at=current,
                finished_at=current,
                policy_version="1.0.3",
                ssot_version="1.0.2",
                entrypoint="allocate",
                cli_args=None,
                db_path=None,
                input_files_json="{}",
                input_hashes_json="{}",
                total_students=1,
                total_allocated=1,
                total_unallocated=0,
                history_metrics_json=None,
                qa_summary_json=None,
                status="success",
                message=None,
            )
        )
        db.insert_trace_snapshot(
            run_id=run_id,
            trace_df=pd.DataFrame({"student_id": [f"student-{tag}"], "stage": ["type"]}),
        )
        db.insert_qa_snapshot(
            run_id=run_id,
            qa_summary_df=pd.DataFrame({"rule_id": [f"QA-{tag}"], "status": ["PASS"]}),
            qa_details_df=pd.DataFrame({"student_id": [f"student-{tag}"]}),
            qa_extras={"allocations": pd.DataFrame({"student_id": [f"student-{tag}"]})},
        )
        db.insert_run_metrics(
            [RunMetricRow(run_id=run_id, metric_key=f"{tag}.students_total", metric_value=1.0)]
        )
    return db


def _cell(model: DataFrameTableModel, row: int = 0, column: int = 0) -> str:
    return str(model.data(model.index(row, column)))


def _assert_saved_rows_unchanged(path: Path) -> None:
    recovered = LocalDatabase(path)
    try:
        assert [run["run_uuid"] for run in recovered.fetch_runs()] == [
            "synthetic-A", "synthetic-B"
        ]
        for run_id, tag in ((1, "A"), (2, "B")):
            trace, _summary, _history = recovered.fetch_trace_snapshot(run_id)
            qa, details, extras = recovered.fetch_qa_snapshot(run_id)
            assert trace is not None and trace.at[0, "student_id"] == f"student-{tag}"
            assert qa is not None and qa.at[0, "rule_id"] == f"QA-{tag}"
            assert details is not None and details.at[0, "student_id"] == f"student-{tag}"
            assert extras["allocations"].at[0, "student_id"] == f"student-{tag}"
    finally:
        recovered.close_all_connections()


@pytest.mark.parametrize("failing_fetch", ["fetch_trace_snapshot", "fetch_qa_snapshot"])
def test_later_selection_failure_clears_stale_data_warns_once_and_retries(
    qapp: QApplication,
    history_db: LocalDatabase,
    monkeypatch: pytest.MonkeyPatch,
    failing_fetch: str,
) -> None:
    errors: list[Exception] = []
    dialog = HistoryDialog(history_db, on_selection_error=errors.append)
    try:
        dialog._run_list.setCurrentRow(0)
        assert _cell(dialog.trace_model) == "student-A"
        assert _cell(dialog.qa_summary_model) == "QA-A"
        assert dialog.qa_details_model.rowCount() == 1
        assert dialog.metrics_model.rowCount() == 1
        assert dialog._qa_extras_model.rowCount() == 1

        original = getattr(history_db, failing_fetch)

        def fail_run_b(run_id: int, *, strict: bool = False) -> object:
            if run_id == 2:
                raise sqlite3.OperationalError("synthetic read failure")
            return original(run_id, strict=strict)

        monkeypatch.setattr(history_db, failing_fetch, fail_run_b)
        # A Qt QListWidget selection triggers the callback, not a direct method call.
        dialog._run_list.setCurrentRow(1)
        assert dialog._run_list.currentRow() == 1
        assert len(errors) == 1 and isinstance(errors[0], sqlite3.OperationalError)
        for model in (
            dialog.trace_model,
            dialog.qa_summary_model,
            dialog.qa_details_model,
            dialog.metrics_model,
            dialog._qa_extras_model,
        ):
            assert model.rowCount() == 0
        assert dialog._qa_extras_list.count() == 0
        _assert_saved_rows_unchanged(history_db.path)

        monkeypatch.setattr(history_db, failing_fetch, original)
        dialog._run_list.setCurrentRow(0)
        dialog._run_list.setCurrentRow(1)
        assert _cell(dialog.trace_model) == "student-B"
        assert _cell(dialog.qa_summary_model) == "QA-B"
        assert dialog.metrics_model.rowCount() == 1
        assert dialog._qa_extras_model.rowCount() == 1
        assert len(errors) == 1  # successful retry did not emit an error
    finally:
        dialog.close()
        qapp.processEvents()


@pytest.mark.parametrize("failing_fetch", ["fetch_trace_snapshot", "fetch_qa_snapshot"])
def test_initial_automatic_selection_failure_is_contained(
    qapp: QApplication,
    history_db: LocalDatabase,
    monkeypatch: pytest.MonkeyPatch,
    failing_fetch: str,
) -> None:
    original = getattr(history_db, failing_fetch)

    def fail_run_b(run_id: int, *, strict: bool = False) -> object:
        if run_id == 2:
            raise sqlite3.OperationalError("synthetic initial read failure")
        return original(run_id, strict=strict)

    monkeypatch.setattr(history_db, failing_fetch, fail_run_b)
    errors: list[Exception] = []
    dialog = HistoryDialog(history_db, on_selection_error=errors.append)
    try:
        assert dialog._run_list.currentRow() == 1
        assert len(errors) == 1
        assert dialog.trace_model.rowCount() == 0
        assert dialog.qa_summary_model.rowCount() == 0
        assert dialog.metrics_model.rowCount() == 0
        _assert_saved_rows_unchanged(history_db.path)
    finally:
        dialog.close()
        qapp.processEvents()


@pytest.mark.parametrize("language", ["fa", "en"])
def test_mainwindow_later_selection_error_uses_localized_existing_warning(
    qapp: QApplication,
    history_db: LocalDatabase,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    language: str,
) -> None:
    monkeypatch.setattr(
        main_window_base,
        "YearDatabaseManager",
        lambda _root: YearDatabaseManager(tmp_path / "years"),
    )
    window = MainWindow()
    window._local_db = history_db
    window._translator = UiTranslator(language)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        staticmethod(lambda _parent, title, detail: warnings.append((title, detail))),
    )
    try:
        window._support_toolbar_actions["run_history"].trigger()
        dialog = window._run_history_dialog
        assert dialog is not None
        dialog._run_list.setCurrentRow(0)
        assert _cell(dialog.trace_model) == "student-A"
        original = history_db.fetch_qa_snapshot

        def fail_run_b(run_id: int, *, strict: bool = False) -> object:
            if run_id == 2:
                raise sqlite3.OperationalError("synthetic later read failure")
            return original(run_id, strict=strict)

        monkeypatch.setattr(history_db, "fetch_qa_snapshot", fail_run_b)
        dialog._run_list.setCurrentRow(1)
        assert warnings == [
            (
                window._t("history.load_failed.title", "Run history unavailable"),
                window._t(
                    "history.load_failed.detail",
                    "Stored runs could not be loaded. Check the local database and retry.",
                ),
            )
        ]
        assert dialog.trace_model.rowCount() == 0
        assert dialog.qa_summary_model.rowCount() == 0
        assert window._run_history_dialog is dialog  # no constructor-only restart
    finally:
        window.close()
        qapp.processEvents()


def test_error_reporting_callback_failure_cannot_escape_selection_signal(
    qapp: QApplication, history_db: LocalDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken_reporter(_error: Exception) -> None:
        raise RuntimeError("simulated warning implementation failure")

    dialog = HistoryDialog(history_db, on_selection_error=broken_reporter)
    try:
        dialog._run_list.setCurrentRow(0)
        def fail_run_b(_run_id: int, *, strict: bool = False) -> object:
            raise sqlite3.OperationalError("synthetic read failure")
        monkeypatch.setattr(history_db, "fetch_trace_snapshot", fail_run_b)
        dialog._run_list.setCurrentRow(1)
        assert dialog.trace_model.rowCount() == 0
        assert dialog.qa_summary_model.rowCount() == 0
    finally:
        dialog.close()
        qapp.processEvents()


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("trace_snapshots", "trace_json"),
        ("qa_snapshots", "qa_summary_json"),
        ("qa_snapshots", "qa_extras_json"),
    ],
)
def test_corrupt_snapshot_json_signals_failure_without_clobbering_persistent_rows(
    qapp: QApplication,
    history_db: LocalDatabase,
    table: str,
    column: str,
) -> None:
    # Temporary database only. A malformed saved payload must not be treated
    # as an absent/empty snapshot by the actual operator History UI.
    errors: list[Exception] = []
    dialog = HistoryDialog(history_db, on_selection_error=errors.append)
    try:
        dialog._run_list.setCurrentRow(0)
        assert _cell(dialog.trace_model) == "student-A"
        with sqlite3.connect(history_db.path) as conn:
            conn.execute(
                f"UPDATE {table} SET {column} = ? WHERE run_id = ?",
                ("{broken-synthetic-json", 2),
            )
            conn.commit()
        dialog._run_list.setCurrentRow(1)
        assert len(errors) == 1
        assert dialog.trace_model.rowCount() == 0
        assert dialog.qa_summary_model.rowCount() == 0
        assert dialog.metrics_model.rowCount() == 0
        with sqlite3.connect(history_db.path) as conn:
            saved = conn.execute(
                f"SELECT {column} FROM {table} WHERE run_id = ?", (2,)
            ).fetchone()
        assert saved == ("{broken-synthetic-json",)
        reopened = LocalDatabase(history_db.path)
        try:
            assert [r["run_uuid"] for r in reopened.fetch_runs()] == [
                "synthetic-A", "synthetic-B"
            ]
            trace_a, _, _ = reopened.fetch_trace_snapshot(1, strict=True)
            assert trace_a is not None and trace_a.at[0, "student_id"] == "student-A"
        finally:
            reopened.close_all_connections()
    finally:
        dialog.close()
        qapp.processEvents()


@pytest.mark.parametrize(
    "nested_payload", [None, ""], ids=["explicit-null", "explicit-empty-string"]
)
def test_corrupt_explicit_nested_qa_extra_clears_selection_and_allows_retry(
    qapp: QApplication,
    history_db: LocalDatabase,
    nested_payload: str | None,
) -> None:
    errors: list[Exception] = []
    dialog = HistoryDialog(history_db, on_selection_error=errors.append)
    try:
        dialog._run_list.setCurrentRow(0)
        assert _cell(dialog.trace_model) == "student-A"
        assert _cell(dialog.qa_summary_model) == "QA-A"
        assert _cell(dialog._qa_extras_model) == "student-A"
        assert dialog.metrics_model.rowCount() == 1
        corrupted = json.dumps({"allocations": nested_payload})
        with sqlite3.connect(history_db.path) as conn:
            original = conn.execute(
                "SELECT qa_extras_json FROM qa_snapshots WHERE run_id = 2"
            ).fetchone()[0]
            conn.execute(
                "UPDATE qa_snapshots SET qa_extras_json = ? WHERE run_id = 2",
                (corrupted,),
            )
            conn.commit()

        dialog._run_list.setCurrentRow(1)
        assert dialog._run_list.currentRow() == 1
        assert len(errors) == 1
        assert isinstance(errors[0], DatabaseOperationError)
        assert "qa_extras.allocations" in str(errors[0])
        for model in (
            dialog.trace_model,
            dialog.qa_summary_model,
            dialog.qa_details_model,
            dialog.metrics_model,
            dialog._qa_extras_model,
        ):
            assert model.rowCount() == 0
        assert dialog._qa_extras_list.count() == 0
        with sqlite3.connect(history_db.path) as conn:
            assert conn.execute(
                "SELECT qa_extras_json FROM qa_snapshots WHERE run_id = 2"
            ).fetchone() == (corrupted,)
            conn.execute(
                "UPDATE qa_snapshots SET qa_extras_json = ? WHERE run_id = 2",
                (original,),
            )
            conn.commit()
        dialog._run_list.setCurrentRow(0)
        dialog._run_list.setCurrentRow(1)
        assert _cell(dialog.trace_model) == "student-B"
        assert _cell(dialog.qa_summary_model) == "QA-B"
        assert _cell(dialog._qa_extras_model) == "student-B"
        assert dialog.metrics_model.rowCount() == 1
        assert len(errors) == 1
        _assert_saved_rows_unchanged(history_db.path)
    finally:
        dialog.close()
        qapp.processEvents()


@pytest.mark.parametrize("language", ["fa", "en"])
def test_dossier_bilingual_identity_direction_and_qa_independence(
    qapp: QApplication, history_db: LocalDatabase, language: str
) -> None:
    with sqlite3.connect(history_db.path) as conn:
        conn.execute(
            """
            UPDATE runs SET status = ?, qa_summary_json = ?, total_allocated = ?,
                total_unallocated = ? WHERE id = ?
            """,
            ("success", json.dumps({"passed": False, "violation_count": 2}), None, 1, 1),
        )
        conn.commit()
    dialog = HistoryDialog(history_db, translator=UiTranslator(language))
    try:
        dialog._run_list.setCurrentRow(0)
        assert dialog.layoutDirection() == (
            Qt.LayoutDirection.RightToLeft if language == "fa"
            else Qt.LayoutDirection.LeftToRight
        )
        assert "synthetic-A" in dialog._identity_label.text()
        assert dialog._qa_outcome_label.text().find(
            "ناموفق" if language == "fa" else "Failed"
        ) >= 0
        assert ("ثبت شده" if language == "fa" else "Recorded success") in (
            dialog._outcome_label.text()
        )
        assert "—" in dialog._counts_label.text()  # unknown is never silently zero
        dialog._run_list.setCurrentRow(1)
        assert ("ثبت نشده" if language == "fa" else "Not recorded") in (
            dialog._qa_outcome_label.text()
        )
        assert "synthetic-A" not in dialog._identity_label.text()
    finally:
        dialog.close()
        qapp.processEvents()


def test_run_specific_output_reference_never_uses_global_last_output(
    qapp: QApplication, history_db: LocalDatabase, monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path
) -> None:
    path_a = r"C:\\synthetic\\run-A.xlsx"
    path_b = r"C:\\synthetic\\run-B.xlsx"
    with sqlite3.connect(history_db.path) as conn:
        conn.execute(
            "UPDATE runs SET input_files_json = ? WHERE id = 1",
            (json.dumps({"output": path_a}),),
        )
        conn.execute(
            "UPDATE runs SET input_files_json = ?, status = ? WHERE id = 2",
            (json.dumps({"output": path_b}), "failed"),
        )
        conn.commit()
    monkeypatch.setattr(
        main_window_base, "YearDatabaseManager",
        lambda _root: YearDatabaseManager(tmp_path / "years"),
    )
    window = MainWindow()
    try:
        window._local_db = history_db
        # Do not persist a synthetic path into the developer/runner QSettings.
        monkeypatch.setattr(type(window._prefs), "last_output_dir", property(lambda _s: path_b))
        window._support_toolbar_actions["run_history"].trigger()
        dialog = window._run_history_dialog
        assert dialog is not None
        dialog._run_list.setCurrentRow(0)
        assert dialog._output_path_edit.text() == path_a
        assert "Recorded success" in dialog._outcome_label.text()
        assert "not verification" in dialog._path_note.text()
        assert dialog._copy_path_button.isEnabled()
        dialog._copy_path_button.click()
        assert QApplication.clipboard().text() == path_a
        dialog._run_list.setCurrentRow(1)
        assert "Recorded failure" in dialog._outcome_label.text()
        assert dialog._output_path_edit.text() == path_b
        with sqlite3.connect(history_db.path) as conn:
            conn.execute(
                "UPDATE runs SET input_files_json = ? WHERE id = 2",
                (json.dumps({"output": None}),),
            )
            conn.commit()
        dialog._run_list.setCurrentRow(0)
        dialog._run_list.setCurrentRow(1)
        assert dialog._output_path_edit.text() == ""
        assert not dialog._copy_path_button.isEnabled()
        assert dialog._recorded_output_path is None
        assert path_b != QApplication.clipboard().text()
    finally:
        window.close()
        qapp.processEvents()


def test_missing_and_valid_empty_snapshots_are_not_conflated(
    qapp: QApplication, history_db: LocalDatabase
) -> None:
    dialog = HistoryDialog(history_db, translator=UiTranslator("en"))
    try:
        with sqlite3.connect(history_db.path) as conn:
            conn.execute("DELETE FROM trace_snapshots WHERE run_id = 2")
            conn.execute("DELETE FROM qa_snapshots WHERE run_id = 2")
            conn.commit()
        dialog._run_list.setCurrentRow(0)
        dialog._run_list.setCurrentRow(1)
        assert dialog._trace_empty.text() == "Not recorded"
        assert dialog._qa_summary_empty.text() == "Not recorded"
        history_db.insert_trace_snapshot(run_id=2, trace_df=pd.DataFrame())
        history_db.insert_qa_snapshot(
            run_id=2, qa_summary_df=pd.DataFrame(), qa_details_df=pd.DataFrame()
        )
        dialog._retry_button.click()  # retry the selected row without a selection change
        assert dialog._trace_empty.text() == "Recorded, but empty"
        assert dialog._qa_summary_empty.text() == "Recorded, but empty"
        assert dialog.trace_model.rowCount() == 0
    finally:
        dialog.close()
        qapp.processEvents()


def test_unreadable_reference_disables_copy_and_does_not_corrupt_qa_disclosure(
    qapp: QApplication, history_db: LocalDatabase
) -> None:
    with sqlite3.connect(history_db.path) as conn:
        conn.execute(
            "UPDATE runs SET input_files_json = ?, qa_summary_json = ? WHERE id = 1",
            ("{synthetic-bad-json", "{synthetic-bad-qa"),
        )
        conn.commit()
    dialog = HistoryDialog(history_db, translator=UiTranslator("en"))
    try:
        dialog._run_list.setCurrentRow(0)
        assert dialog._output_path_edit.text() == ""
        assert dialog._output_path_edit.placeholderText() == "Unreadable recorded data"
        assert not dialog._copy_path_button.isEnabled()
        assert "Unreadable recorded data" in dialog._qa_outcome_label.text()
        assert dialog.trace_model.rowCount() == 1  # corrupted run metadata != missing Trace
    finally:
        dialog.close()
        qapp.processEvents()


def test_retry_after_transient_selection_failure_never_copies_stale_run_path(
    qapp: QApplication, history_db: LocalDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    with sqlite3.connect(history_db.path) as conn:
        conn.execute(
            "UPDATE runs SET input_files_json = ? WHERE id = 1",
            (json.dumps({"output": r"C:\\synthetic\\A.xlsx"}),),
        )
        conn.execute(
            "UPDATE runs SET input_files_json = ? WHERE id = 2",
            (json.dumps({"output": r"C:\\synthetic\\B.xlsx"}),),
        )
        conn.commit()
    errors: list[Exception] = []
    dialog = HistoryDialog(history_db, on_selection_error=errors.append)
    try:
        dialog._run_list.setCurrentRow(0)
        assert dialog._copy_path_button.isEnabled()
        original = history_db.fetch_trace_snapshot
        call_count = 0

        def fail_once(run_id: int, *, strict: bool = False) -> object:
            nonlocal call_count
            if run_id == 2 and call_count == 0:
                call_count += 1
                raise sqlite3.OperationalError("synthetic transient read error")
            return original(run_id, strict=strict)

        monkeypatch.setattr(history_db, "fetch_trace_snapshot", fail_once)
        dialog._run_list.setCurrentRow(1)
        assert len(errors) == 1
        assert not dialog._copy_path_button.isEnabled()
        assert dialog._output_path_edit.text() == ""
        assert dialog.trace_model.rowCount() == 0
        dialog._retry_button.click()
        assert dialog._output_path_edit.text() == r"C:\\synthetic\\B.xlsx"
        assert dialog._copy_path_button.isEnabled()
        assert _cell(dialog.trace_model) == "student-B"
    finally:
        dialog.close()
        qapp.processEvents()


def test_dossier_keyboard_selection_and_retry_accessibility(
    qapp: QApplication, history_db: LocalDatabase
) -> None:
    dialog = HistoryDialog(history_db, translator=UiTranslator("en"))
    try:
        dialog.show()
        qapp.processEvents()
        assert dialog._run_list.accessibleName() == "Recorded runs"
        assert dialog._output_path_edit.accessibleName() == "Recorded output path for this run"
        dialog._run_list.setCurrentRow(1)
        dialog._run_list.setFocus()
        QTest.keyClick(dialog._run_list, Qt.Key.Key_Up)
        assert dialog._run_list.currentRow() == 0
        assert dialog._selected_run_id == 1
        dialog._retry_button.setFocus()
        QTest.keyClick(dialog._retry_button, Qt.Key.Key_Space)
        assert dialog._selected_run_id == 1
        assert _cell(dialog.trace_model) == "student-A"
    finally:
        dialog.close()
        qapp.processEvents()


def test_recorded_output_reference_survives_database_reopen(
    qapp: QApplication, history_db: LocalDatabase
) -> None:
    recorded = r"C:\\synthetic\\archive.xlsx"
    with sqlite3.connect(history_db.path) as conn:
        conn.execute(
            "UPDATE runs SET input_files_json = ? WHERE id = 1",
            (json.dumps({"output": recorded}),),
        )
        conn.commit()
    history_db.close_all_connections()
    reopened = LocalDatabase(history_db.path)
    dialog = HistoryDialog(reopened, translator=UiTranslator("en"))
    try:
        dialog._run_list.setCurrentRow(0)
        assert dialog._output_path_edit.text() == recorded
        assert "not verification" in dialog._path_note.text()
    finally:
        dialog.close()
        reopened.close_all_connections()
        qapp.processEvents()
