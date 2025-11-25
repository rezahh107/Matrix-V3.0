"""دیالوگ مرور تاریخچهٔ QA/Trace ذخیره‌شده در SQLite."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.infra.local_database import LocalDatabase

Row = Mapping[str, Any]


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

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
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

    def __init__(self, db: LocalDatabase, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._db = db
        self._runs: Sequence[Row] = []
        self.setWindowTitle("History Snapshots")

        self._run_list = QListWidget(self)
        self._run_list.currentRowChanged.connect(self._on_run_selected)

        self._trace_model = DataFrameTableModel()
        self._trace_view = QTableView(self)
        self._trace_view.setModel(self._trace_model)
        self._trace_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._trace_view.horizontalHeader().setStretchLastSection(True)
        self._trace_view.verticalHeader().setVisible(False)
        self._trace_empty = QLabel("No trace snapshot", self)
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
        self._qa_extras_empty = QLabel("No QA extras", self)
        self._qa_extras_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._metrics_model = DataFrameTableModel()
        self._metrics_view = QTableView(self)
        self._metrics_view.setModel(self._metrics_model)
        self._metrics_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._metrics_view.horizontalHeader().setStretchLastSection(True)
        self._metrics_view.verticalHeader().setVisible(False)
        self._metrics_empty = QLabel("No metrics stored", self)
        self._metrics_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)

        qa_tabs = QTabWidget(self)
        qa_tabs.addTab(self._wrap_widget(self._qa_summary_view), "QA Summary")
        qa_tabs.addTab(self._wrap_widget(self._qa_details_view), "QA Details")
        qa_tabs.addTab(
            self._wrap_widget(self._qa_extras_list, self._qa_extras_view, self._qa_extras_empty),
            "QA Extras",
        )

        right_tabs = QTabWidget(self)
        right_tabs.addTab(self._wrap_widget(self._metrics_view, self._metrics_empty), "Metrics")
        right_tabs.addTab(self._wrap_widget(self._trace_view, self._trace_empty), "Trace")
        right_tabs.addTab(qa_tabs, "QA")

        layout = QHBoxLayout(self)
        layout.addWidget(self._run_list, 1)
        layout.addWidget(right_tabs, 3)

        self.resize(1024, 640)
        self._load_runs()

    # Helpers -----------------------------------------------------------
    def _wrap_widget(self, *widgets: QWidget) -> QWidget:
        container = QWidget(self)
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(8, 8, 8, 8)
        vbox.setSpacing(6)
        for widget in widgets:
            vbox.addWidget(widget)
        return container

    def _load_runs(self) -> None:
        self._runs = cast(Sequence[Row], self._db.fetch_runs())
        self._run_list.clear()
        for row in self._runs:
            started = row["started_at"]
            self._run_list.addItem(f"#{row['id']} | {row['run_uuid']} | {started}")
        if self._runs:
            self._run_list.setCurrentRow(len(self._runs) - 1)
        else:
            self._clear_views()

    def _clear_views(self) -> None:
        self._trace_model.update(pd.DataFrame())
        self._qa_summary_model.update(pd.DataFrame())
        self._qa_details_model.update(pd.DataFrame())
        self._qa_extras_model.update(pd.DataFrame())
        self._qa_extras = {}
        self._qa_extras_list.clear()
        self._metrics_model.update(pd.DataFrame())
        self._update_empty_states()

    def _on_run_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._runs):
            self._clear_views()
            return
        run_row = self._runs[row]
        run_id = int(run_row["id"])
        metrics_df = self._rows_to_dataframe(self._db.fetch_metrics_for_run(run_id))
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
        self._update_empty_states()

    def _update_empty_states(self) -> None:
        is_trace_empty = self._trace_model.rowCount() == 0
        self._trace_view.setVisible(not is_trace_empty)
        self._trace_empty.setVisible(is_trace_empty)
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
        trace_df, summary_df, history_df = self._db.fetch_trace_snapshot(run_id)
        if trace_df is not None:
            if summary_df is not None:
                trace_df.attrs["summary_df"] = summary_df
            if history_df is not None:
                trace_df.attrs["history_info_df"] = history_df
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
