from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.infra.local_database import DatabaseHealthStatus, DatabaseHealthSummary
from app.ui.theme import Theme

__all__ = ["DatabaseStatusWidget"]


class DatabaseStatusWidget(QWidget):
    """Compact database health summary; semantic colors come only from global QSS."""

    databaseManagerRequested = Signal()  # noqa: N815

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._icon_label = QLabel("●", self)
        self._icon_label.setObjectName("databaseHealthIcon")
        self._text_label = QLabel(self)
        self._text_label.setObjectName("databaseHealthText")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.micro, 0, theme.micro, 0)
        layout.setSpacing(theme.icon_to_text)
        layout.addWidget(
            self._icon_label,
            0,
            Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter,
        )
        layout.addWidget(
            self._text_label,
            0,
            Qt.AlignmentFlag.AlignTrailing | Qt.AlignmentFlag.AlignVCenter,
        )
        layout.addStretch()
        self.setLayout(layout)
        self.setAccessibleName("database-status-widget")
        self._apply_theme_colors(theme)

    def _apply_theme_colors(self, theme: Theme) -> None:
        self._theme = theme
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, theme.text_primary)
        palette.setColor(QPalette.ColorRole.Text, theme.text_primary)
        self.setPalette(palette)

    def set_summary(self, summary: DatabaseHealthSummary) -> None:
        """Update wording plus a semantic-state property; color is never the only cue."""

        state = self._state_for_status(summary.status)
        self._icon_label.setProperty("databaseHealth", state)
        self._text_label.setProperty("databaseHealth", state)
        for label in (self._icon_label, self._text_label):
            label.style().unpolish(label)
            label.style().polish(label)
        self._text_label.setText(summary.message)
        self.setAccessibleDescription(f"Database health: {summary.message}")
        self.setToolTip(self._build_tooltip(summary))

    @staticmethod
    def _state_for_status(status: DatabaseHealthStatus) -> str:
        if status is DatabaseHealthStatus.OK:
            return "ok"
        if status is DatabaseHealthStatus.DEGRADED:
            return "warning"
        return "error"

    def _build_tooltip(self, summary: DatabaseHealthSummary) -> str:
        parts: list[str] = []
        if summary.counts:
            parts.append(" | ".join(f"{key}: {value:,}" for key, value in summary.counts.items()))
        if summary.last_updated:
            last = summary.last_updated
            if isinstance(last, datetime):
                parts.append(f"آخرین به‌روزرسانی: {last.isoformat(timespec='seconds')}")
        return summary.message if not parts else " — ".join(parts)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mousePressEvent(event)
        self.databaseManagerRequested.emit()
