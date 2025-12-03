from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.core.common.types import JoinKeyEntityType
from app.ui.viewmodels.qa_dashboard_vm import QADashboardVM


class QADashboardDialog(QDialog):
    """Lightweight dashboard showing join-key validation summaries."""

    def __init__(self, vm: QADashboardVM, parent: object | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._vm = vm
        self.setWindowTitle("QA Dashboard")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Join-key issues per run"))
        table = QTableWidget(self)
        entities: list[JoinKeyEntityType] = ["student", "mentor", "school", "form"]
        table.setColumnCount(len(entities) + 1)
        headers = ["Run"] + [entity.title() for entity in entities]
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(vm.summaries))
        for row_index, summary in enumerate(vm.summaries):
            self._set_item(table, row_index, 0, summary.run_label)
            for col_index, entity in enumerate(entities, start=1):
                count = vm.issue_count(row_index, entity)
                self._set_item(table, row_index, col_index, str(count))
        table.resizeColumnsToContents()
        layout.addWidget(table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    @staticmethod
    def _set_item(table: QTableWidget, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, column, item)

    @property
    def view_model(self) -> QADashboardVM:
        return self._vm
