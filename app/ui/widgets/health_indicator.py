from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QWidget

from app.infra.health import HealthSummary
from app.ui.texts import UiTranslator


@dataclass(frozen=True)
class HealthCallbacks:
    fetch_summary: Callable[[], HealthSummary | None]
    export_report: Callable[[], str | None]


class HealthIndicatorWidget(QFrame):
    """نمایش compact سلامت با حفظ دو action و summary موجود."""

    def __init__(
        self,
        callbacks: HealthCallbacks,
        parent: QWidget | None = None,
        translator: UiTranslator | None = None,
    ) -> None:
        super().__init__(parent)
        self._callbacks = callbacks
        self._translator = translator
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("healthIndicator")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)

        self._status_label = QLabel(self._t("health.na", "System health: n/a"), self)
        self._status_label.setObjectName("healthStatus")
        self._status_label.setWordWrap(False)
        layout.addWidget(self._status_label, 1)

        self._btn_details = QPushButton(self._t("health.details", "View details"), self)
        self._btn_details.setProperty("variant", "secondary")
        self._btn_export = QPushButton(self._t("health.export", "Export report"), self)
        self._btn_export.setProperty("variant", "secondary")
        self._btn_details.clicked.connect(self._on_view_details)
        self._btn_export.clicked.connect(self._on_export)
        self._btn_details.setEnabled(False)
        self._btn_export.setEnabled(False)
        layout.addWidget(self._btn_details)
        layout.addWidget(self._btn_export)

        self._current_summary: HealthSummary | None = None
        self.refresh()

    def update_translator(self, translator: UiTranslator) -> None:
        self._translator = translator
        self._btn_details.setText(self._t("health.details", "View details"))
        self._btn_export.setText(self._t("health.export", "Export report"))
        self.refresh()

    def refresh(self) -> None:
        summary = None
        try:
            summary = self._callbacks.fetch_summary()
        except Exception:
            summary = None
        self._current_summary = summary
        if summary is None:
            self._status_label.setText(self._t("health.unavailable", "System health: unavailable"))
            self._set_health_state("none")
            self._btn_details.setEnabled(False)
            self._btn_export.setEnabled(False)
            return
        template = self._t("health.summary", "System health: {summary}")
        self._status_label.setText(template.format(summary=summary.summary_text))
        self._set_health_state(summary.status.lower())
        self._btn_details.setEnabled(True)
        self._btn_export.setEnabled(True)

    def _set_health_state(self, state: str) -> None:
        normalized = state if state in {"ok", "warning", "error"} else "none"
        self._status_label.setProperty("health", normalized)
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
        QMessageBox.information(self, self._t("health.details_title", "Health details"), details)

    def _on_export(self) -> None:
        try:
            path = self._callbacks.export_report()
        except Exception as exc:
            QMessageBox.critical(self, self._t("health.export_failed", "Export failed"), str(exc))
            return
        if path:
            template = self._t("health.exported_detail", "Report saved to: {path}")
            QMessageBox.information(
                self,
                self._t("health.exported", "Report exported"),
                template.format(path=path),
            )

    def _t(self, key: str, fallback: str) -> str:
        if self._translator is None:
            return fallback
        return self._translator.text(key, fallback)
