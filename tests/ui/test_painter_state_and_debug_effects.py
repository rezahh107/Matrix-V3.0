"""Tests for painter guard and dashboard card offscreen rendering."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPen, QTransform
from PySide6.QtWidgets import QApplication, QWidget

from app.ui.effects import SafeDropShadowEffect, SafeOpacityEffect
from app.ui.utils import painter_state
from app.ui.widgets import DashboardCard
from tests.ui.qt_offscreen_harness import (
    assert_image_has_content,
    painter_on_image,
    render_widget_offscreen,
)


def test_painter_state_restores_properties(qtbot: pytest.QtBot, qapp: QApplication) -> None:
    image = QImage(32, 24, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)

    with painter_on_image(image) as painter:
        assert painter.isActive()

        original_transform = QTransform(painter.transform())
        original_pen = QPen(painter.pen())

        with painter_state(painter):
            painter.translate(5, 3)
            custom_pen = QPen(original_pen)
            custom_pen.setWidth(custom_pen.width() + 2)
            painter.setPen(custom_pen)
            painter.drawRect(0, 0, 10, 10)

        assert painter.transform() == original_transform
        assert painter.pen() == original_pen


def test_safe_effects_render_without_state_leak(qtbot: pytest.QtBot, qapp: QApplication) -> None:
    widget = QWidget()
    widget.resize(160, 120)
    widget.setGraphicsEffect(SafeDropShadowEffect("shadow_test", widget))
    inner = QWidget(widget)
    inner.setGraphicsEffect(SafeOpacityEffect("opacity_test", inner))
    inner.resize(80, 60)

    image = render_widget_offscreen(qtbot, widget, widget.size())
    assert_image_has_content(image)


def test_dashboard_card_render_offscreen(qtbot: pytest.QtBot, qapp: QApplication) -> None:
    card = DashboardCard("title", "desc")
    image = render_widget_offscreen(qtbot, card, QSize(200, 140))
    assert_image_has_content(image)


@pytest.mark.parametrize("_run", range(2))
def test_dashboard_card_multiple_renders(
    qtbot: pytest.QtBot, qapp: QApplication, _run: int
) -> None:
    card = DashboardCard("title", "desc")
    image = render_widget_offscreen(qtbot, card, QSize(220, 160))
    assert_image_has_content(image)
