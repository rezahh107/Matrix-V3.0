from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from app.infra.local_database import DatabaseHealthStatus, DatabaseHealthSummary
from app.ui.fonts import get_app_font
from app.ui.theme import Theme

__all__ = ["DatabaseStatusWidget"]


class DatabaseStatusWidget(QWidget):
    """ویجت کوچک برای نمایش وضعیت پایگاه‌داده در نوار وضعیت.

    این ویجت تنها مسئول نمایش است و وضعیت را از خلاصه‌ای که بیرون از آن
    (مثلاً توسط پنجره اصلی) تهیه می‌شود دریافت می‌کند.
    """

    databaseManagerRequested = Signal()  # noqa: N815 - نام سیگنال Qt

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._icon_label = QLabel("●", self)
        self._text_label = QLabel(self)
        self._text_label.setFont(get_app_font())
        self._icon_label.setFont(get_app_font())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)
        layout.addWidget(
            self._icon_label,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        layout.addWidget(
            self._text_label,
            0,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        layout.addStretch()
        self.setLayout(layout)
        self.setAccessibleName("database-status-widget")
        self._apply_theme_colors(theme)

    def _apply_theme_colors(self, theme: Theme) -> None:
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.WindowText, theme.text_primary)
        palette.setColor(QPalette.ColorRole.Text, theme.text_primary)
        self.setPalette(palette)
        self._text_label.setStyleSheet(f"color: {theme.colors.text};")

    def set_summary(self, summary: DatabaseHealthSummary) -> None:
        """به‌روزرسانی متن و رنگ آیکن بر اساس خلاصه وضعیت پایگاه‌داده."""

        color = self._color_for_status(summary.status)
        self._icon_label.setStyleSheet(f"color: {color}; font-size: 10pt;")
        self._text_label.setText(summary.message)
        tooltip = self._build_tooltip(summary)
        self.setToolTip(tooltip)

    def _color_for_status(self, status: DatabaseHealthStatus) -> str:
        if status is DatabaseHealthStatus.OK:
            return "#2ecc71"
        if status is DatabaseHealthStatus.DEGRADED:
            return "#f1c40f"
        return "#e74c3c"

    def _build_tooltip(self, summary: DatabaseHealthSummary) -> str:
        parts: list[str] = []
        if summary.counts:
            counts_text = " | ".join(f"{key}: {value:,}" for key, value in summary.counts.items())
            parts.append(counts_text)
        if summary.last_updated:
            last = summary.last_updated
            if isinstance(last, datetime):
                parts.append(f"آخرین به‌روزرسانی: {last.isoformat(timespec='seconds')}")
        if not parts:
            return summary.message
        return " — ".join(parts)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - امضای Qt
        super().mousePressEvent(event)
        self.databaseManagerRequested.emit()
