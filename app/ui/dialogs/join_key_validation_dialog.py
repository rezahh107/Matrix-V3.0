from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.ui.viewmodels.join_key_validation_vm import JoinKeyValidationVM


class JoinKeyValidationDialog(QDialog):
    """Simple dialog to present join-key validation issues."""

    def __init__(self, validation_vm: JoinKeyValidationVM, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._vm = validation_vm
        self.setWindowTitle("Join Key Validation")
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Rows with invalid join keys:"))
        table = QTableWidget(self)
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Row", "Column", "Value", "Error"])
        table.setRowCount(len(validation_vm.issues))
        for idx, issue in enumerate(validation_vm.issues):
            self._set_item(table, idx, 0, str(issue.row_index))
            self._set_item(table, idx, 1, issue.column)
            self._set_item(table, idx, 2, str(issue.raw_value))
            self._set_item(table, idx, 3, issue.error_code)
        layout.addWidget(table)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _set_item(table: QTableWidget, row: int, column: int, text: str) -> None:
        table.setItem(row, column, QTableWidgetItem(text))

    @property
    def view_model(self) -> JoinKeyValidationVM:
        return self._vm
