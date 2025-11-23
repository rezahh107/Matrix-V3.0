from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QLabel, QHBoxLayout, QStatusBar, QWidget

from app.ui.fonts import get_app_font
from app.ui.theme import Theme
from app.infra.local_database import DatabaseHealthStatus, DatabaseHealthSummary

__all__ = ["ThemedStatusBar", "DatabaseStatusWidget"]


class ThemedStatusBar(QStatusBar):
    """نوار وضعیت با اعمال رنگ و فونت هماهنگ با تم فعال."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setSizeGripEnabled(False)
        self.apply_theme(theme)
        self.setFont(get_app_font())

    def apply_theme(self, theme: Theme) -> None:
        """به‌روزرسانی رنگ پس‌زمینه و برچسب‌ها بر اساس تم."""

        self._theme = theme
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, theme.card)
        palette.setColor(QPalette.ColorRole.Base, theme.card)
        palette.setColor(QPalette.ColorRole.Text, theme.text_primary)
        palette.setColor(QPalette.ColorRole.WindowText, theme.text_primary)
        self.setPalette(palette)
        self.setAutoFillBackground(True)

        self.setStyleSheet(
            f"QStatusBar {{"
            f"background: {theme.colors.card};"
            f"border-top: 1px solid {theme.colors.border};"
            f"padding: {theme.spacing_xs}px {theme.spacing_md}px;"
            f"}}"
            f"QLabel#languagePill, QLabel#statusPill {{"
            f"background: {theme.colors.surface_alt};"
            f"border: 1px solid {theme.colors.border};"
            f"border-radius: {theme.radius_sm}px;"
            f"padding: {theme.spacing_xs}px {theme.spacing_md}px;"
            f"font-weight: 700;"
            f"}}"
        )

    def refresh_fonts(self) -> None:
        """بازنشانی فونت برای هماهنگی با فونت سراسری."""

        self.setFont(get_app_font())
        for label in self.findChildren(QLabel):
            label.setFont(get_app_font())


class DatabaseStatusWidget(QWidget):
    """ویجت کوچک برای نمایش وضعیت پایگاه‌داده در نوار وضعیت."""

    def __init__(self, theme: Theme, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self._icon_label = QLabel("●", self)
        self._text_label = QLabel(self)
        self._text_label.setFont(get_app_font())
        self._icon_label.setFont(get_app_font())
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)
        layout.addWidget(self._icon_label, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._text_label, 0, Qt.AlignRight | Qt.AlignVCenter)
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
            counts_text = " | ".join(
                f"{key}: {value:,}" for key, value in summary.counts.items()
            )
            parts.append(counts_text)
        if summary.last_updated:
            last = summary.last_updated
            if isinstance(last, datetime):
                parts.append(f"آخرین به‌روزرسانی: {last.isoformat(timespec='seconds')}")
        if not parts:
            return summary.message
        return " — ".join(parts)
