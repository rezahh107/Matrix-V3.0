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

from app.ui.viewmodels.student_domain_validation_vm import StudentDomainValidationVM


class StudentDomainValidationDialog(QDialog):
    """Simple dialog to present student domain validation issues."""

    def __init__(self, vm: StudentDomainValidationVM, parent: object | None = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self._vm = vm
        self.setWindowTitle("Student Domain Validation")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Domain issues detected in student data"))
        table = QTableWidget(self)
        headers = [
            "Row",
            "Group",
            "Graduation",
            "Allowed",
            "Error",
        ]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(vm.total_issues)
        for row_index, issue in enumerate(vm.issues):
            self._set_item(table, row_index, 0, str(issue.row_index))
            self._set_item(table, row_index, 1, str(issue.group_code))
            self._set_item(table, row_index, 2, str(issue.graduation_status))
            self._set_item(table, row_index, 3, ", ".join(map(str, issue.allowed_statuses)))
            self._set_item(table, row_index, 4, issue.error_code)
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
    def view_model(self) -> StudentDomainValidationVM:
        return self._vm
