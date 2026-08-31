"""ویجت کارت داشبورد با هدر و بدنه انعطاف‌پذیر."""

from __future__ import annotations

import logging
from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtGui import QPaintEvent
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.theme import Theme, apply_card_shadow

__all__ = ["DashboardCard"]
LOGGER = logging.getLogger(__name__)


class DashboardCard(QFrame):
    """کارت داشبورد با عنوان، توضیح و محتوای سفارشی."""

    def __init__(
        self,
        title: str,
        description: str,
        parent: QWidget | None = None,
        *,
        max_height: int | None = None,
        theme: Theme | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardCard")
        self._theme = theme or Theme()
        policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        if max_height is not None:
            policy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.setMaximumHeight(max_height)
        self.setSizePolicy(policy)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(8)
        self._body_container = QScrollArea(self)
        self._body_container.setWidgetResizable(True)
        self._body_container.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._body_container.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._body_container.setFrameShape(QFrame.Shape.NoFrame)
        self._body_widget = QWidget(self._body_container)
        self._body = QVBoxLayout(self._body_widget)
        self._body.setContentsMargins(0, 0, 0, 0)
        self._body.setSpacing(4)
        self._body_container.setWidget(self._body_widget)

        header = QVBoxLayout()
        header.setSpacing(2)
        self._title_label = QLabel(title)
        self._title_label.setObjectName("dashboardCardTitle")
        self._description_label = QLabel(description)
        self._description_label.setObjectName("dashboardCardDescription")
        self._description_label.setWordWrap(True)
        header.addWidget(self._title_label)
        header.addWidget(self._description_label)
        self._layout.addLayout(header)
        self._layout.addWidget(self._body_container)

        apply_card_shadow(self)
        self.apply_theme(self._theme)

    def body_layout(self) -> QVBoxLayout:
        return self._body

    def add_widgets(self, widgets: Iterable[QWidget]) -> None:
        for widget in widgets:
            self._body.addWidget(widget)

    def clear_body(self) -> None:
        while self._body.count():
            item = self._body.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)

    def set_header(self, title: str, description: str) -> None:
        self._title_label.setText(title)
        self._description_label.setText(description)

    def apply_theme(self, theme: Theme) -> None:
        """فقط spacing/state را به‌روزرسانی می‌کند؛ styles.qss visual authority است."""

        self._theme = theme
        self._layout.setContentsMargins(
            theme.spacing_md,
            theme.spacing_md,
            theme.spacing_md,
            theme.spacing_md,
        )
        self._layout.setSpacing(theme.spacing_sm)
        self._body.setSpacing(theme.spacing_xs + 2)

    def _apply_shadow(self, spec: object | None) -> None:
        apply_card_shadow(self)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - امضای Qt
        LOGGER.debug(
            "DashboardCard.paintEvent | widget=%s effect=%s rect=%s",
            self,
            self.graphicsEffect(),
            event.rect(),
        )
        super().paintEvent(event)
