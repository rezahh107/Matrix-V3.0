from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class UnknownIssueSample:
    entity_type: str
    row_index: int | None
    column: str
    raw_value: str
    error_code: str


@dataclass(frozen=True)
class UnknownsReportSummary:
    total: int
    by_entity_type: dict[str, int]
    by_code: dict[str, int]
    samples: list[UnknownIssueSample]


def load_unknowns_report(path: Path) -> dict[str, object]:
    data = path.read_text(encoding="utf-8")
    parsed = json.loads(data)
    if not isinstance(parsed, dict):
        raise ValueError("Unknowns report must be a JSON object.")
    return parsed


def summarize_unknowns_report(
    report: Mapping[str, object], *, sample_limit: int = 5
) -> UnknownsReportSummary:
    issues_raw = report.get("issues") or []
    issues_list = issues_raw if isinstance(issues_raw, list) else []
    samples: list[UnknownIssueSample] = []
    by_entity: dict[str, int] = {}
    by_code: dict[str, int] = {}

    for entry in issues_list:
        if not isinstance(entry, Mapping):
            continue
        entity_type = str(entry.get("entity_type") or "")
        column = str(entry.get("column") or "")
        raw_value = entry.get("raw_value")
        error_code = str(entry.get("error_code") or "")
        row_index = entry.get("row_index")
        row_value = int(row_index) if isinstance(row_index, int) else None
        sample = UnknownIssueSample(
            entity_type=entity_type,
            row_index=row_value,
            column=column,
            raw_value=str(raw_value) if raw_value is not None else "",
            error_code=error_code,
        )
        if len(samples) < sample_limit:
            samples.append(sample)
        by_entity[entity_type] = by_entity.get(entity_type, 0) + 1
        by_code[error_code] = by_code.get(error_code, 0) + 1

    summary_raw = report.get("summary") if isinstance(report, Mapping) else None
    total = len(issues_list)
    if isinstance(summary_raw, Mapping):
        total = int(summary_raw.get("total", total))
        summary_entities = summary_raw.get("by_entity_type")
        if isinstance(summary_entities, Mapping):
            by_entity = {
                str(key): int(value) for key, value in summary_entities.items()
            }
        summary_codes = summary_raw.get("by_code")
        if isinstance(summary_codes, Mapping):
            by_code = {str(key): int(value) for key, value in summary_codes.items()}

    return UnknownsReportSummary(
        total=int(total),
        by_entity_type=by_entity,
        by_code=by_code,
        samples=samples,
    )


class UnknownDataDialog(QDialog):
    """Dialog for UNKNOWN-ASK-01 decision gating."""

    def __init__(
        self,
        summary: UnknownsReportSummary,
        *,
        report_path: Path,
        title: str,
        body: str,
        counts_text: str,
        headers: Sequence[str],
        cancel_text: str,
        proceed_text: str,
        open_report_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._summary = summary
        self._report_path = report_path
        self._proceed = False

        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(body))
        layout.addWidget(QLabel(counts_text))

        table = QTableWidget(self)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(list(headers))
        table.setRowCount(len(summary.samples))
        for idx, sample in enumerate(summary.samples):
            self._set_item(table, idx, 0, sample.entity_type)
            self._set_item(
                table,
                idx,
                1,
                "-" if sample.row_index is None else str(sample.row_index),
            )
            self._set_item(table, idx, 2, sample.column)
            self._set_item(table, idx, 3, sample.raw_value)
            self._set_item(table, idx, 4, sample.error_code)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(table)

        buttons = QDialogButtonBox(parent=self)
        cancel_button = buttons.addButton(
            cancel_text, QDialogButtonBox.ButtonRole.RejectRole
        )
        proceed_button = buttons.addButton(
            proceed_text, QDialogButtonBox.ButtonRole.AcceptRole
        )
        open_button = buttons.addButton(
            open_report_text, QDialogButtonBox.ButtonRole.ActionRole
        )
        cancel_button.setDefault(True)
        cancel_button.setAutoDefault(True)
        proceed_button.clicked.connect(self._on_proceed)
        cancel_button.clicked.connect(self.reject)
        open_button.clicked.connect(self._open_report_folder)
        layout.addWidget(buttons)

    def _open_report_folder(self) -> None:
        folder = self._report_path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _on_proceed(self) -> None:
        self._proceed = True
        self.accept()

    @property
    def should_proceed(self) -> bool:
        return self._proceed

    @staticmethod
    def _set_item(table: QTableWidget, row: int, column: int, text: str) -> None:
        table.setItem(row, column, QTableWidgetItem(text))

    @property
    def summary(self) -> UnknownsReportSummary:
        return self._summary
