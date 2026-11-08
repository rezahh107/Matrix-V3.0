"""دیالوگ مرور تاریخچهٔ QA/Trace ذخیره‌شده در SQLite."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, QPersistentModelIndex, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.infra.local_database import LocalDatabase
from app.ui.i18n import Language
from app.ui.texts import UiTranslator

Row = Mapping[str, Any]
logger = logging.getLogger(__name__)


class DataFrameTableModel(QAbstractTableModel):
    """مدل عمومی فقط‌خواندنی برای نمایش دیتافریم.

    این مدل ستون‌ها را به ترتیب ورودی حفظ می‌کند و مقادیر NaN را به
    رشتهٔ خالی تبدیل می‌نماید تا نمایش UI پایدار باشد.
    """

    def __init__(self, df: pd.DataFrame | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._df = self._normalize(df)

    @staticmethod
    def _normalize(df: pd.DataFrame | None) -> pd.DataFrame:
        if df is None:
            return pd.DataFrame()
        return df.copy()

    def update(self, df: pd.DataFrame | None) -> None:
        self.beginResetModel()
        self._df = self._normalize(df)
        self.endResetModel()

    # Qt overrides ------------------------------------------------------
    def rowCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]  # noqa: N802 - امضای Qt
        if parent and parent.isValid():
            return 0
        return len(self._df.index)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # type: ignore[override]  # noqa: N802 - امضای Qt
        if parent and parent.isValid():
            return 0
        return len(self._df.columns)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        if not index.isValid() or role not in {
            Qt.ItemDataRole.DisplayRole,
            Qt.ItemDataRole.EditRole,
        }:
            return None
        value = self._df.iloc[index.row(), index.column()]
        if pd.isna(value):
            return ""
        return str(value)

    def headerData(  # noqa: N802 - امضای Qt
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:  # noqa: N802 - امضای Qt
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._df.columns):
                return str(self._df.columns[section])
        else:
            return str(section + 1)
        return None


class HistoryDialog(QDialog):
    """دیالوگ برای انتخاب اجرا و مشاهدهٔ Snapshot های QA/Trace."""

    def __init__(
        self,
        db: LocalDatabase,
        parent: QWidget | None = None,
        *,
        on_selection_error: Callable[[Exception], None] | None = None,
        translator: UiTranslator | None = None,
    ) -> None:
        super().__init__(parent)
        self._db = db
        self._on_selection_error = on_selection_error
        self._translator = translator or UiTranslator(Language.EN)
        self._runs: Sequence[Row] = []
        self._metrics_by_run: dict[int, Sequence[Row]] = {}
        self._selected_run_id: int | None = None
        self._recorded_output_path: str | None = None
        self.setWindowTitle(self._t("history.dossier.title", "Run Review Dossier"))
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if self._translator.language == "fa"
            else Qt.LayoutDirection.LeftToRight
        )

        self._run_list = QListWidget(self)
        self._run_list.setAccessibleName(
            self._t("history.dossier.run_list", "Recorded runs")
        )
        self._run_list.currentRowChanged.connect(self._on_run_selected)

        self._trace_model = DataFrameTableModel()
        self._trace_view = QTableView(self)
        self._trace_view.setModel(self._trace_model)
        self._trace_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._trace_view.horizontalHeader().setStretchLastSection(True)
        self._trace_view.verticalHeader().setVisible(False)
        self._trace_empty = QLabel(self._t("history.dossier.not_recorded", "Not recorded"), self)
        self._trace_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._qa_summary_model = DataFrameTableModel()
        self._qa_details_model = DataFrameTableModel()
        self._qa_extras_model = DataFrameTableModel()
        self._qa_extras: dict[str, pd.DataFrame] = {}

        self._qa_summary_view = QTableView(self)
        self._qa_summary_view.setModel(self._qa_summary_model)
        self._qa_summary_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._qa_summary_view.horizontalHeader().setStretchLastSection(True)
        self._qa_summary_view.verticalHeader().setVisible(False)

        self._qa_details_view = QTableView(self)
        self._qa_details_view.setModel(self._qa_details_model)
        self._qa_details_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._qa_details_view.horizontalHeader().setStretchLastSection(True)
        self._qa_details_view.verticalHeader().setVisible(False)

        self._qa_extras_list = QListWidget(self)
        self._qa_extras_list.currentRowChanged.connect(self._on_extra_selected)
        self._qa_extras_view = QTableView(self)
        self._qa_extras_view.setModel(self._qa_extras_model)
        self._qa_extras_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._qa_extras_view.horizontalHeader().setStretchLastSection(True)
        self._qa_extras_view.verticalHeader().setVisible(False)
        self._qa_extras_empty = QLabel(
            self._t("history.dossier.not_recorded", "Not recorded"), self
        )
        self._qa_extras_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._metrics_model = DataFrameTableModel()
        self._metrics_view = QTableView(self)
        self._metrics_view.setModel(self._metrics_model)
        self._metrics_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._metrics_view.horizontalHeader().setStretchLastSection(True)
        self._metrics_view.verticalHeader().setVisible(False)
        self._metrics_empty = QLabel(self._t("history.dossier.not_recorded", "Not recorded"), self)
        self._metrics_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._qa_summary_empty = QLabel(self)
        self._qa_summary_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qa_details_empty = QLabel(self)
        self._qa_details_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        qa_tabs = QTabWidget(self)
        qa_tabs.addTab(
            self._wrap_widget(self._qa_summary_view, self._qa_summary_empty),
            self._t("history.dossier.qa_summary", "QA Summary"),
        )
        qa_tabs.addTab(
            self._wrap_widget(self._qa_details_view, self._qa_details_empty),
            self._t("history.dossier.qa_details", "QA Details"),
        )
        qa_tabs.addTab(
            self._wrap_widget(self._qa_extras_list, self._qa_extras_view, self._qa_extras_empty),
            self._t("history.dossier.qa_extras", "QA Extras"),
        )

        right_tabs = QTabWidget(self)
        right_tabs.addTab(
            self._wrap_widget(self._trace_view, self._trace_empty),
            self._t("history.dossier.trace", "Trace"),
        )
        right_tabs.addTab(qa_tabs, self._t("history.dossier.qa_tab", "QA Evidence"))
        right_tabs.addTab(
            self._wrap_widget(self._metrics_view, self._metrics_empty),
            self._t("history.dossier.metrics", "Metrics"),
        )

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(6)
        self._dossier_header = QLabel(self._t("history.dossier.title", "Run Review Dossier"), self)
        self._dossier_header.setObjectName("runDossierHeading")
        right_layout.addWidget(self._dossier_header)
        self._dossier_lines: list[QLabel] = []
        for name in (
            "runIdentity", "runOutcome", "runTimes", "runCounts", "runVersions",
            "runQaOutcome", "runEvidence",
        ):
            label = QLabel(self)
            label.setObjectName(name)
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            right_layout.addWidget(label)
            self._dossier_lines.append(label)
        (
            self._identity_label, self._outcome_label, self._times_label,
            self._counts_label, self._versions_label, self._qa_outcome_label,
            self._evidence_label,
        ) = self._dossier_lines

        self._path_label = QLabel(
            self._t("history.dossier.output", "Recorded output path for this run"), self
        )
        right_layout.addWidget(self._path_label)
        path_row = QHBoxLayout()
        self._output_path_edit = QLineEdit(self)
        self._output_path_edit.setReadOnly(True)
        self._output_path_edit.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self._output_path_edit.setAccessibleName(self._path_label.text())
        self._copy_path_button = QPushButton(
            self._t("history.dossier.copy", "Copy recorded path"), self
        )
        self._copy_path_button.setProperty("variant", "secondary")
        self._copy_path_button.clicked.connect(self._copy_recorded_path)
        path_row.addWidget(self._output_path_edit, 1)
        path_row.addWidget(self._copy_path_button)
        right_layout.addLayout(path_row)
        self._path_note = QLabel(
            self._t(
                "history.dossier.output_warning",
                "This is a stored reference, not verification of the file's origin or integrity.",
            ), self
        )
        self._path_note.setWordWrap(True)
        right_layout.addWidget(self._path_note)
        self._retry_button = QPushButton(
            self._t("history.dossier.retry", "Retry selected run / refresh history"), self
        )
        self._retry_button.setProperty("variant", "secondary")
        self._retry_button.clicked.connect(self._retry_read)
        right_layout.addWidget(self._retry_button)
        right_layout.addWidget(right_tabs, 1)

        # The dossier remains reachable with long messages, large fonts or a small screen.
        right_scroll = QScrollArea(self)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(right_panel)
        layout = QHBoxLayout(self)
        layout.addWidget(self._run_list, 1)
        layout.addWidget(right_scroll, 3)

        self.resize(1024, 640)
        self._clear_views()
        self._load_runs()
        self._run_list.setFocus()

    # Helpers -----------------------------------------------------------
    def _wrap_widget(self, *widgets: QWidget) -> QWidget:
        container = QWidget(self)
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)
        for widget in widgets:
            vbox.addWidget(widget)
        return container

    def _t(self, key: str, fallback: str) -> str:
        return self._translator.text(key, fallback)

    @staticmethod
    def _field(row: Row, key: str) -> object:
        # Old history test adapters may provide only a subset of run fields.
        return row[key] if key in row.keys() else None

    @staticmethod
    def _value(value: object) -> str:
        if value is None or value == "":
            return "—"
        return str(value)

    @staticmethod
    def _ltr(value: object) -> str:
        # Unicode isolates prevent a UUID or mixed-direction value from reordering the label.
        return "\u2066" + str(value) + "\u2069"

    def _availability(self, frame: pd.DataFrame | None) -> str:
        if frame is None:
            return self._t("history.dossier.not_recorded", "Not recorded")
        if frame.empty:
            return self._t("history.dossier.recorded_empty", "Recorded, but empty")
        return self._t("history.dossier.available", "Available")

    def _run_item_text(self, row: Row) -> str:
        status = self._field(row, "status")
        status_text = {
            "success": self._t("history.dossier.execution_success", "Recorded success"),
            "failed": self._t("history.dossier.execution_failure", "Recorded failure"),
        }.get(status, self._value(status))
        return (
            self._ltr(f"#{row['id']}")
            + " · "
            + self._value(self._field(row, "entrypoint"))
            + " · "
            + self._ltr(self._value(self._field(row, "started_at")))
            + " · "
            + status_text
        )

    def _load_runs(self) -> None:
        # Clearing first also makes a failed refresh safe: no prior run remains actionable.
        self._runs = []
        self._metrics_by_run = {}
        self._run_list.clear()
        self._clear_views()
        runs = cast(Sequence[Row], self._db.fetch_runs())
        metrics = self._db.fetch_metrics_for_runs([int(r["id"]) for r in runs])
        self._runs, self._metrics_by_run = runs, metrics
        for row in self._runs:
            self._run_list.addItem(self._run_item_text(row))
        if self._runs:
            self._run_list.setCurrentRow(len(self._runs) - 1)
        else:
            self._identity_label.setText(
                self._t("history.dossier.no_runs", "No historical runs recorded")
            )

    def _clear_views(self) -> None:
        self._selected_run_id = None
        self._recorded_output_path = None
        self._copy_path_button.setEnabled(False)
        self._output_path_edit.clear()
        self._output_path_edit.setPlaceholderText(
            self._t("history.dossier.not_recorded", "Not recorded")
        )
        for label in self._dossier_lines:
            label.clear()
        self._identity_label.setText(
            self._t("history.dossier.select_run", "Select a run to review its record")
        )
        self._trace_model.update(pd.DataFrame())
        self._qa_summary_model.update(pd.DataFrame())
        self._qa_details_model.update(pd.DataFrame())
        self._qa_extras_model.update(pd.DataFrame())
        self._qa_extras = {}
        self._qa_extras_list.clear()
        self._metrics_model.update(pd.DataFrame())
        for label in (
            self._trace_empty, self._qa_summary_empty, self._qa_details_empty,
            self._qa_extras_empty, self._metrics_empty,
        ):
            label.setText(self._t("history.dossier.not_recorded", "Not recorded"))
        self._update_empty_states()

    def _qa_result(self, raw_json: object) -> str:
        if raw_json is None or raw_json == "":
            return self._t("history.dossier.not_recorded", "Not recorded")
        try:
            payload = json.loads(raw_json) if isinstance(raw_json, str) else None
        except (TypeError, ValueError):
            return self._t("history.dossier.unreadable", "Unreadable recorded data")
        if not isinstance(payload, dict):
            return self._t("history.dossier.unreadable", "Unreadable recorded data")
        if "passed" not in payload:
            return self._t("history.dossier.unknown", "Result not recorded")
        passed = payload["passed"]
        if not isinstance(passed, bool):
            return self._t("history.dossier.unreadable", "Unreadable recorded data")
        verdict = self._t(
            "history.dossier.qa_pass" if passed else "history.dossier.qa_fail",
            "Passed" if passed else "Failed",
        )
        count = payload.get("violation_count")
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
            verdict += " · " + self._t(
                "history.dossier.violations", "Violations: {count}"
            ).format(count=count)
        elif "violation_count" in payload:
            verdict += " · " + self._t(
                "history.dossier.invalid_count", "Recorded violation count is unreadable"
            )
        return verdict

    def _stored_output(self, raw_json: object) -> tuple[str | None, bool]:
        if raw_json is None or raw_json == "":
            return None, False
        try:
            payload = json.loads(raw_json) if isinstance(raw_json, str) else None
        except (ValueError, TypeError):
            return None, True
        if not isinstance(payload, dict):
            return None, True
        path = payload.get("output")
        if path is None:
            return None, False
        if not isinstance(path, str):
            return None, True
        if not path.strip() or "\x00" in path:
            return None, True
        return path, False

    def _render_record(
        self,
        run_row: Row,
        trace: pd.DataFrame | None,
        qa_summary: pd.DataFrame | None,
        qa_details: pd.DataFrame | None,
        metrics: pd.DataFrame,
    ) -> None:
        run_id = int(run_row["id"])
        operation = self._value(self._field(run_row, "entrypoint"))
        self._identity_label.setText(
            self._t("history.dossier.identity", "Run #{id} · {operation}").format(
                id=run_id, operation=operation
            ) + " · " + self._ltr(self._value(self._field(run_row, "run_uuid")))
        )
        status = self._field(run_row, "status")
        status_text = {
            "success": self._t("history.dossier.execution_success", "Recorded success"),
            "failed": self._t("history.dossier.execution_failure", "Recorded failure"),
        }.get(status, self._value(status))
        self._outcome_label.setText(
            self._t("history.dossier.execution", "Execution: {status}").format(
                status=status_text
            )
            + (
                " · " + str(self._field(run_row, "message"))
                if self._field(run_row, "message")
                else ""
            )
        )
        self._times_label.setText(
            self._t("history.dossier.times", "Started: {start} · Finished: {end}").format(
                start=self._ltr(self._value(self._field(run_row, "started_at"))),
                end=self._ltr(self._value(self._field(run_row, "finished_at"))),
            )
        )
        self._counts_label.setText(
            self._t(
                "history.dossier.counts",
                "Students: {students} · Allocated: {allocated} · Unallocated: {unallocated}",
            ).format(
                students=self._value(self._field(run_row, "total_students")),
                allocated=self._value(self._field(run_row, "total_allocated")),
                unallocated=self._value(self._field(run_row, "total_unallocated")),
            )
        )
        self._versions_label.setText(
            self._t(
                "history.dossier.versions",
                "Recorded policy: {policy} · SSoT: {ssot}",
            ).format(
                policy=self._ltr(self._value(self._field(run_row, "policy_version"))),
                ssot=self._ltr(self._value(self._field(run_row, "ssot_version"))),
            )
        )
        self._qa_outcome_label.setText(
            self._t("history.dossier.qa_outcome", "Recorded QA result: {value}").format(
                value=self._qa_result(self._field(run_row, "qa_summary_json"))
            )
        )
        self._evidence_label.setText(
            self._t(
                "history.dossier.evidence",
                "QA summary: {qa} · Trace: {trace} · Metrics: {metrics}",
            ).format(
                qa=self._availability(qa_summary),
                trace=self._availability(trace),
                metrics=(
                    self._availability(metrics)
                    if not metrics.empty
                    else self._t("history.dossier.not_recorded", "Not recorded")
                ),
            )
        )
        self._trace_empty.setText(self._availability(trace))
        self._qa_summary_empty.setText(self._availability(qa_summary))
        self._qa_details_empty.setText(self._availability(qa_details))
        self._metrics_empty.setText(
            self._t("history.dossier.not_recorded", "Not recorded")
        )
        # Empty extras can also mean a stored empty map; the API cannot tell which.
        self._qa_extras_empty.setText(
            self._t("history.dossier.no_extra_rows", "No additional QA rows available")
        )
        path, invalid = self._stored_output(self._field(run_row, "input_files_json"))
        if invalid:
            self._output_path_edit.setPlaceholderText(
                self._t("history.dossier.unreadable", "Unreadable recorded data")
            )
        elif path is not None:
            self._recorded_output_path = path
            self._output_path_edit.setText(path)
            self._copy_path_button.setEnabled(True)
        self._selected_run_id = run_id

    def _on_run_selected(self, row: int) -> None:
        # Always revoke the previous run's content and copy action before reading.
        self._clear_views()
        if row < 0 or row >= len(self._runs):
            return
        try:
            run_id = int(self._runs[row]["id"])
            if isinstance(self._db, LocalDatabase):
                fresh_row = self._db.fetch_run_by_id(run_id)
                if fresh_row is None:
                    raise RuntimeError("Selected historical run no longer exists")
                run_row: Row = fresh_row
            else:
                run_row = self._runs[row]
            # The list and the dossier must describe the same refreshed record.
            self._run_list.item(row).setText(self._run_item_text(run_row))
            metrics_df = self._rows_to_dataframe(
                cast(Sequence[Row], self._metrics_by_run.get(run_id, []))
            )
            trace_df, qa_summary_df, qa_details_df, qa_extras = self._load_snapshots(run_id)
            self._metrics_model.update(metrics_df)
            self._trace_model.update(trace_df)
            self._qa_summary_model.update(qa_summary_df)
            self._qa_details_model.update(qa_details_df)
            self._qa_extras = qa_extras or {}
            self._qa_extras_list.clear()
            for key in sorted(self._qa_extras):
                self._qa_extras_list.addItem(str(key))
            if self._qa_extras:
                self._qa_extras_list.setCurrentRow(0)
            else:
                self._qa_extras_model.update(pd.DataFrame())
            self._render_record(run_row, trace_df, qa_summary_df, qa_details_df, metrics_df)
            self._update_empty_states()
        except Exception as exc:
            logger.exception("Failed to read selected history run %s", row)
            self._clear_views()
            self._identity_label.setText(
                self._t(
                    "history.dossier.read_failed",
                    "The selected run could not be read. Retry or select another run.",
                )
            )
            self._report_selection_error(exc)

    def _retry_read(self) -> None:
        row = self._run_list.currentRow()
        if row >= 0:
            self._on_run_selected(row)
        else:
            try:
                self._load_runs()
            except Exception as exc:
                logger.exception("Failed to refresh historical run list")
                self._clear_views()
                self._report_selection_error(exc)

    def _copy_recorded_path(self) -> None:
        row = self._run_list.currentRow()
        if self._recorded_output_path is None or self._selected_run_id is None:
            return
        if row < 0 or row >= len(self._runs):
            return
        if int(self._runs[row]["id"]) != self._selected_run_id:
            return
        QApplication.clipboard().setText(self._recorded_output_path)

    def _report_selection_error(self, error: Exception) -> None:
        """Keep Qt signal callbacks safe even if error presentation itself fails."""
        try:
            if self._on_selection_error is not None:
                self._on_selection_error(error)
            else:
                QMessageBox.warning(
                    self,
                    self._t("history.load_failed.title", "Run history unavailable"),
                    self._t(
                        "history.load_failed.detail",
                        "Stored runs could not be loaded. Check the local database and retry.",
                    ),
                )
        except Exception:
            logger.exception("Failed to report a history selection error")

    def _update_empty_states(self) -> None:
        is_trace_empty = self._trace_model.rowCount() == 0
        self._trace_view.setVisible(not is_trace_empty)
        self._trace_empty.setVisible(is_trace_empty)
        is_qa_summary_empty = self._qa_summary_model.rowCount() == 0
        self._qa_summary_view.setVisible(not is_qa_summary_empty)
        self._qa_summary_empty.setVisible(is_qa_summary_empty)
        is_qa_details_empty = self._qa_details_model.rowCount() == 0
        self._qa_details_view.setVisible(not is_qa_details_empty)
        self._qa_details_empty.setVisible(is_qa_details_empty)
        is_metrics_empty = self._metrics_model.rowCount() == 0
        self._metrics_view.setVisible(not is_metrics_empty)
        self._metrics_empty.setVisible(is_metrics_empty)
        is_extras_empty = self._qa_extras_model.rowCount() == 0
        self._qa_extras_view.setVisible(not is_extras_empty)
        self._qa_extras_empty.setVisible(is_extras_empty)

    def _load_snapshots(
        self, run_id: int
    ) -> tuple[
        pd.DataFrame | None, pd.DataFrame | None, pd.DataFrame | None, dict[str, pd.DataFrame]
    ]:
        # Real LocalDatabase can report corrupt serialized snapshots. Keep the
        # older one-argument duck-typed test adapters usable without weakening
        # the production read path.
        if isinstance(self._db, LocalDatabase):
            trace_df, _summary_df, _history_df = self._db.fetch_trace_snapshot(
                run_id, strict=True
            )
            qa_summary_df, qa_details_df, qa_extras = self._db.fetch_qa_snapshot(
                run_id, strict=True
            )
        else:
            trace_df, _summary_df, _history_df = self._db.fetch_trace_snapshot(run_id)
            qa_summary_df, qa_details_df, qa_extras = self._db.fetch_qa_snapshot(run_id)
        return trace_df, qa_summary_df, qa_details_df, qa_extras

    def _on_extra_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._qa_extras):
            self._qa_extras_model.update(pd.DataFrame())
            self._update_empty_states()
            return
        key = self._qa_extras_list.item(row).text()
        frame = self._qa_extras.get(key, pd.DataFrame())
        self._qa_extras_model.update(frame)
        self._update_empty_states()

    @staticmethod
    def _rows_to_dataframe(rows: Sequence[Row]) -> pd.DataFrame:
        if not rows:
            return pd.DataFrame()
        normalized = [dict(cast(dict[str, Any], row)) for row in rows]
        return pd.DataFrame(normalized)

    # Exposed for tests -------------------------------------------------
    @property
    def trace_model(self) -> DataFrameTableModel:
        return self._trace_model

    @property
    def qa_summary_model(self) -> DataFrameTableModel:
        return self._qa_summary_model

    @property
    def qa_details_model(self) -> DataFrameTableModel:
        return self._qa_details_model

    @property
    def metrics_model(self) -> DataFrameTableModel:
        return self._metrics_model
