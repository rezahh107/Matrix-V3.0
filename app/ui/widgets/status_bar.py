from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QStatusBar, QWidget

from app.ui.theme import Theme

from .database_status_widget import DatabaseStatusWidget

__all__ = ["ThemedStatusBar", "DatabaseStatusWidget"]


class ThemedStatusBar(QStatusBar):
    """نوار وضعیت؛ visual skin آن منحصراً از styles.qss می‌آید."""

    def __init__(self, theme: Theme, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme
        self.setSizeGripEnabled(False)
        self.apply_theme(theme)

    def apply_theme(self, theme: Theme) -> None:
        """فقط palette/state را به‌روزرسانی می‌کند، نه stylesheet یا font محلی."""

        self._theme = theme
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, theme.card)
        palette.setColor(QPalette.ColorRole.Base, theme.card)
        palette.setColor(QPalette.ColorRole.Text, theme.text_primary)
        palette.setColor(QPalette.ColorRole.WindowText, theme.text_primary)
        self.setPalette(palette)
        self.setAutoFillBackground(True)
