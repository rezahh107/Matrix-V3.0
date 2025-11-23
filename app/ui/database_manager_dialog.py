"""دیالوگ مدیریت پایگاه داده برای نمایش سلامت و عملیات بازنشانی."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
try:  # pragma: no cover - وابستگی Qt ممکن است در CI غایب باشد
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QDialog,
        QGridLayout,
        QHeaderView,
        QHBoxLayout,
        QLabel,
        QMessageBox,
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
    QGridLayout = QHeaderView = QLabel = QMessageBox = QPushButton = QTableWidget = QTableWidgetItem = QVBoxLayout = QWidget = None  # type: ignore
    _QT_AVAILABLE = False
    _QT_IMPORT_ERROR = exc

from app.infra.local_database import (
    DatabaseSchemaDiagnostics,
    LocalDatabase,
)
from app.infra.year_database_manager import YearDatabaseInfo

__all__ = ["DatabaseManagerDialog", "_QT_AVAILABLE"]


class DatabaseManagerDialog(QDialog):
    """پنجرهٔ مدیریت پایگاه‌داده با خلاصهٔ سلامت، تشخیص ستون‌ها و بازنشانی ایمن."""

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
        self.diagnostics: DatabaseSchemaDiagnostics | None = None
        self.setWindowTitle("مدیریت پایگاه داده")
        self.resize(900, 600)
        self._build_ui()
        self._refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._path_label = QLabel(self)
        self._path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self._path_label)

        grid = QGridLayout()
        self._schema_label = QLabel(self)
        self._module_label = QLabel(self)
        self._schema_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._module_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        grid.addWidget(QLabel("نسخهٔ Schema (انتظار/فعلی):", self), 0, 0)
        grid.addWidget(self._schema_label, 0, 1)
        grid.addWidget(QLabel("مسیر ماژول SQLite:", self), 1, 0)
        grid.addWidget(self._module_label, 1, 1)
        layout.addLayout(grid)

        tables_label = QLabel("خلاصه جداول کلیدی", self)
        layout.addWidget(tables_label)
        self._counts_table = QTableWidget(self)
        self._counts_table.setColumnCount(3)
        self._counts_table.setHorizontalHeaderLabels(["جدول", "تعداد ردیف", "ستون‌های مفقود"])
        header = self._counts_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        layout.addWidget(self._counts_table)

        issues_label = QLabel("مشکلات Schema", self)
        layout.addWidget(issues_label)
        self._issues_table = QTableWidget(self)
        self._issues_table.setColumnCount(2)
        self._issues_table.setHorizontalHeaderLabels(["جدول", "ستون‌های مفقود"])
        header2 = self._issues_table.horizontalHeader()
        header2.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header2.setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self._issues_table)

        btn_row = QHBoxLayout()
        self._btn_refresh = QPushButton("به‌روزرسانی", self)
        self._btn_reset = QPushButton("بکاپ و بازنشانی پایگاه‌داده", self)
        self._btn_refresh.clicked.connect(self._refresh)
        self._btn_reset.clicked.connect(self._backup_and_reset)
        btn_row.addWidget(self._btn_refresh)
        btn_row.addWidget(self._btn_reset)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

    def _refresh(self) -> None:
        summary = self.db.get_database_health_summary()
        self.diagnostics = self.db.get_schema_diagnostics()
        self._path_label.setText(
            f"سال فعال: {self.year_info.year_id}\nمسیر پایگاه‌داده: {self.year_info.path}"
        )
        actual = self.diagnostics.actual_schema_version
        self._schema_label.setText(f"{self.diagnostics.expected_schema_version} / {actual}")
        self._module_label.setText(self.diagnostics.module_path)
        self._populate_counts_table(summary.counts, self.diagnostics.tables)
        self._populate_issues_table(self.diagnostics.tables)
        status_prefix = {
            "ok": "✅",
            "degraded": "⚠️",
            "unavailable": "❌",
        }.get(summary.status.value, "")
        self.setWindowTitle(f"مدیریت پایگاه داده {status_prefix}")

    def _populate_counts_table(
        self, counts: dict[str, int], table_diags: Iterable[object]
    ) -> None:
        rows: list[tuple[str, str, str]] = []
        for diag in table_diags:
            missing = ", ".join(diag.missing_required_columns)
            row_count = diag.row_count if diag.row_count is not None else counts.get(diag.name, 0)
            rows.append((diag.name, str(row_count), missing))
        self._counts_table.setRowCount(len(rows))
        for idx, (name, count, missing) in enumerate(rows):
            self._counts_table.setItem(idx, 0, QTableWidgetItem(name))
            self._counts_table.setItem(idx, 1, QTableWidgetItem(count))
            self._counts_table.setItem(idx, 2, QTableWidgetItem(missing))

    def _populate_issues_table(self, table_diags: Iterable[object]) -> None:
        issues = [
            (diag.name, ", ".join(diag.missing_required_columns))
            for diag in table_diags
            if diag.missing_required_columns
        ]
        self._issues_table.setRowCount(len(issues))
        for idx, (name, missing) in enumerate(issues):
            self._issues_table.setItem(idx, 0, QTableWidgetItem(name))
            self._issues_table.setItem(idx, 1, QTableWidgetItem(missing))

    def _backup_and_reset(self) -> None:
        backup_path: Path | None = None
        try:
            backup_path = self.db.backup_and_reset()
        except Exception as exc:  # pragma: no cover - مسیر خطا نادر
            QMessageBox.critical(
                self,
                "خطا در بازنشانی",
                f"بازنشانی پایگاه‌داده با خطا مواجه شد: {exc}",
            )
            return
        message = "پایگاه‌داده با موفقیت بازنشانی شد."
        if backup_path is not None:
            message += f"\nبکاپ: {backup_path}"
        QMessageBox.information(self, "انجام شد", message)
        self._refresh()
