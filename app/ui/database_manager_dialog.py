"""پنجرهٔ مدیریت پایگاه داده برای مشاهده سال جاری."""

from __future__ import annotations

import pandas as pd
try:  # pragma: no cover - وابستگی Qt ممکن است در CI غایب باشد
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QDialog,
        QHeaderView,
        QLabel,
        QPushButton,
        QTableWidget,
        QTableWidgetItem,
        QVBoxLayout,
        QWidget,
    )
    _QT_AVAILABLE = True
except Exception as exc:  # pragma: no cover - fallback
    Qt = None  # type: ignore
    QDialog = object  # type: ignore
    QHeaderView = QLabel = QPushButton = QTableWidget = QTableWidgetItem = QVBoxLayout = QWidget = None  # type: ignore
    _QT_AVAILABLE = False
    _QT_IMPORT_ERROR = exc

from app.infra.local_database import LocalDatabase
from app.infra.year_database_manager import YearDatabaseInfo


class DatabaseManagerDialog(QDialog):
    """نمایش سادهٔ اطلاعات پایگاه دادهٔ سالیانه."""

    def __init__(
        self,
        *,
        db: LocalDatabase,
        year_info: YearDatabaseInfo,
        parent: QWidget | None = None,
    ) -> None:
        if not _QT_AVAILABLE:
            raise RuntimeError(f"Qt bindings unavailable: {_QT_IMPORT_ERROR}")
        super().__init__(parent)
        self.db = db
        self.year_info = year_info
        self.setWindowTitle("مدیریت پایگاه داده")
        self.resize(720, 480)
        self._build_ui()
        self._refresh_tables()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        info_label = QLabel(
            f"سال فعال: {self.year_info.year_id}\nمسیر: {self.year_info.path}\nنسخهٔ schema: {self.year_info.schema_version}"
        )
        info_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(info_label)

        self.table_widget = QTableWidget(self)
        self.table_widget.setColumnCount(2)
        self.table_widget.setHorizontalHeaderLabels(["جدول", "تعداد ردیف"])
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        layout.addWidget(self.table_widget)

        self.preview_label = QLabel("پیش‌نمایش جدول انتخاب‌شده")
        layout.addWidget(self.preview_label)

        self.preview_widget = QTableWidget(self)
        layout.addWidget(self.preview_widget)

        refresh_btn = QPushButton("به‌روزرسانی")
        refresh_btn.clicked.connect(self._refresh_tables)
        layout.addWidget(refresh_btn)

        self.table_widget.itemSelectionChanged.connect(self._load_preview)

    def _refresh_tables(self) -> None:
        df = self.db.list_tables_with_counts()
        self.table_widget.setRowCount(len(df))
        for idx, row in df.iterrows():
            self.table_widget.setItem(idx, 0, QTableWidgetItem(str(row["table"])))
            self.table_widget.setItem(idx, 1, QTableWidgetItem(str(row["row_count"])))
        if len(df):
            self.table_widget.selectRow(0)
        else:
            self.preview_widget.clear()

    def _load_preview(self) -> None:
        items = self.table_widget.selectedItems()
        if not items:
            return
        table_name = items[0].text()
        df = self.db.preview_table(table_name, limit=50)
        self._populate_preview(df)

    def _populate_preview(self, df: pd.DataFrame) -> None:
        self.preview_widget.clear()
        if df.empty:
            self.preview_widget.setRowCount(0)
            self.preview_widget.setColumnCount(0)
            return
        self.preview_widget.setRowCount(len(df.index))
        self.preview_widget.setColumnCount(len(df.columns))
        self.preview_widget.setHorizontalHeaderLabels([str(col) for col in df.columns])
        for r_idx, (_, row) in enumerate(df.iterrows()):
            for c_idx, value in enumerate(row):
                self.preview_widget.setItem(r_idx, c_idx, QTableWidgetItem(str(value)))
        self.preview_widget.resizeColumnsToContents()
