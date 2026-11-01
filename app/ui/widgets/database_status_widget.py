from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.infra.local_database import (
    DatabaseHealthReason,
    DatabaseHealthStatus,
    DatabaseHealthSummary,
)
from app.ui.i18n import Language
from app.ui.texts import UiTranslator
from app.ui.theme import Theme

__all__ = ["DatabaseStatusWidget"]

# Legacy count keys are fixed schema labels, not arbitrary diagnostic strings.
_COUNT_LABELS = {
    "دانش‌آموز": ("database.health.students", "Students", "دانش‌آموز"),
    "پشتیبان": ("database.health.mentors", "Mentors", "پشتیبان"),
    "اجرا": ("database.health.runs", "Runs", "اجرا"),
}
_HEALTH_LABELS = {
    "ready": ("database.health.ready", "Database: Ready", "پایگاه‌داده: آماده"),
    "needs_review": (
        "database.health.needs_review",
        "Database: Needs attention",
        "پایگاه‌داده: نیاز به بررسی",
    ),
    "missing_file": (
        "database.health.missing_file",
        "Database: File not found",
        "پایگاه‌داده: فایل یافت نشد",
    ),
    "connection_error": (
        "database.health.connection_error",
        "Database: Connection error",
        "پایگاه‌داده: خطای اتصال",
    ),
    "unavailable": (
        "database.health.unavailable",
        "Database: Unavailable",
        "پایگاه‌داده: در دسترس نیست",
    ),
}

# A quiet status bar needs short labels; the tooltip and accessibility retain the
# complete reason. Persian strings remain unchanged where they already fit.
_COMPACT_EN_LABELS = {
    "ready": ("database.health.compact.ready", "DB: Ready"),
    "needs_review": ("database.health.compact.needs_review", "DB: Check"),
    "missing_file": ("database.health.compact.missing_file", "DB: No file"),
    "connection_error": ("database.health.compact.connection_error", "DB: SQL error"),
    "unavailable": ("database.health.compact.unavailable", "DB: Unavailable"),
}


class DatabaseStatusWidget(QWidget):
    """Compact localized database health; severity colors remain global QSS-owned."""

    databaseManagerRequested = Signal()  # noqa: N815

    def __init__(
        self,
        theme: Theme,
        parent: QWidget | None = None,
        *,
        translator: UiTranslator | None = None,
    ) -> None:
        super().__init__(parent)
        self._theme = theme
        self._translator = translator or UiTranslator(Language.EN)
        self._summary: DatabaseHealthSummary | None = None
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
        self._apply_theme_colors(theme)
        self.set_translator(self._translator)

    def _apply_theme_colors(self, theme: Theme) -> None:
        self._theme = theme
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, theme.text_primary)
        palette.setColor(QPalette.ColorRole.Text, theme.text_primary)
        self.setPalette(palette)

    def _tr(self, key: str, english: str, persian: str) -> str:
        fallback = persian if self._translator.language_enum is Language.FA else english
        return self._translator.text(key, fallback)

    def set_translator(self, translator: UiTranslator) -> None:
        """Rerender observed health without querying the database again."""
        self._translator = translator
        self.setLayoutDirection(
            Qt.LayoutDirection.RightToLeft
            if translator.language_enum is Language.FA
            else Qt.LayoutDirection.LeftToRight
        )
        self.setAccessibleName(
            self._tr("database.health.accessible_name", "Database health", "سلامت پایگاه‌داده")
        )
        if self._summary is not None:
            self.set_summary(self._summary)

    def set_summary(self, summary: DatabaseHealthSummary) -> None:
        """Present stable status/reason, never parse free-form diagnostic messages."""
        self._summary = summary
        state = self._state_for_status(summary.status)
        self._icon_label.setProperty("databaseHealth", state)
        self._text_label.setProperty("databaseHealth", state)
        for label in (self._icon_label, self._text_label):
            label.style().unpolish(label)
            label.style().polish(label)

        message = self._localized_status(summary)
        self._text_label.setText(self._localized_status(summary, compact=True))
        self.setAccessibleDescription(message)
        self.setToolTip(self._build_tooltip(summary, message))

    def _localized_status(self, summary: DatabaseHealthSummary, *, compact: bool = False) -> str:
        # Severity wins over inconsistent or absent reasons: no invented failure.
        if summary.status is DatabaseHealthStatus.OK:
            label = "ready"
        elif summary.status is DatabaseHealthStatus.DEGRADED:
            label = "needs_review"
        elif summary.reason is DatabaseHealthReason.MISSING_FILE:
            label = "missing_file"
        elif summary.reason is DatabaseHealthReason.CONNECTION_ERROR:
            label = "connection_error"
        else:
            label = "unavailable"
        if compact and self._translator.language_enum is Language.EN:
            key, fallback = _COMPACT_EN_LABELS[label]
            return self._translator.text(key, fallback)
        return self._tr(*_HEALTH_LABELS[label])

    @staticmethod
    def _state_for_status(status: DatabaseHealthStatus) -> str:
        if status is DatabaseHealthStatus.OK:
            return "ok"
        if status is DatabaseHealthStatus.DEGRADED:
            return "warning"
        return "error"

    def _build_tooltip(self, summary: DatabaseHealthSummary, message: str) -> str:
        parts = [message]
        if summary.counts:
            counts = []
            for key, value in summary.counts.items():
                label = self._tr(*_COUNT_LABELS[key]) if key in _COUNT_LABELS else key
                counts.append(f"{label}: {value:,}")
            parts.append(" | ".join(counts))
        if isinstance(summary.last_updated, datetime):
            checked = self._tr("database.health.last_checked", "Last checked", "آخرین بررسی")
            parts.append(f"{checked}: {summary.last_updated.isoformat(timespec='seconds')}")
        return " — ".join(parts)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        super().mousePressEvent(event)
        self.databaseManagerRequested.emit()
