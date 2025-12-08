from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.infra.health import HealthSummary


@dataclass(frozen=True)
class HealthCallbacks:
    fetch_summary: Callable[[], HealthSummary | None]
    export_report: Callable[[], str | None]


class HealthIndicatorWidget(QFrame):
    """ویجت ساده برای نمایش وضعیت سلامت و دکمهٔ خروجی گزارش."""

    def __init__(self, callbacks: HealthCallbacks, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._callbacks = callbacks
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("healthIndicator")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(12)

        self._status_label = QLabel("System health: n/a", self)
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label, 1)

        buttons_layout = QVBoxLayout()
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.setSpacing(4)
        self._btn_details = QPushButton("View details", self)
        self._btn_export = QPushButton("Export report for technical support / language model", self)
        self._btn_details.clicked.connect(self._on_view_details)
        self._btn_export.clicked.connect(self._on_export)
        self._btn_details.setEnabled(False)
        self._btn_export.setEnabled(False)
        buttons_layout.addWidget(self._btn_details)
        buttons_layout.addWidget(self._btn_export)
        layout.addLayout(buttons_layout)

        self._current_summary: HealthSummary | None = None
        self.refresh()

    def refresh(self) -> None:
        summary = None
        try:
            summary = self._callbacks.fetch_summary()
        except Exception:
            summary = None
        self._current_summary = summary
        if summary is None:
            self._status_label.setText("System health: unavailable")
            self._status_label.setProperty("health", "none")
            self._btn_details.setEnabled(False)
            self._btn_export.setEnabled(False)
            return
        self._status_label.setText(summary.summary_text)
        self._status_label.setProperty("health", summary.status.lower())
        self._btn_details.setEnabled(True)
        self._btn_export.setEnabled(True)
        self._status_label.style().unpolish(self._status_label)
        self._status_label.style().polish(self._status_label)

    def _on_view_details(self) -> None:
        if self._current_summary is None:
            return
        counts = self._current_summary.counts
        issue_lines = [
            f"{item.issue_code} ({item.severity}): {item.count}"
            for item in self._current_summary.issues_summary
        ]
        details = "\n".join(
            [
                f"P0: {counts.get('P0', 0)}",
                f"P1: {counts.get('P1', 0)}",
                f"P2: {counts.get('P2', 0)}",
            ]
        )
        if issue_lines:
            details = details + "\n" + "\n".join(issue_lines)
        QMessageBox.information(self, "Health details", details)

    def _on_export(self) -> None:
        try:
            path = self._callbacks.export_report()
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        if path:
            QMessageBox.information(self, "Report exported", f"Report saved to: {path}")
