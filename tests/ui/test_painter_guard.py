"""Lightweight tests for painter guard and safe effects."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from app.ui.effects import SafeDropShadowEffect, SafeOpacityEffect
from app.ui.utils import assert_painter_active, painter_guard as painter_guard_module
from tests.ui.qt_offscreen_harness import assert_image_has_content, painter_on_image

pytest.importorskip(
    "PySide6.QtWidgets",
    exc_type=ImportError,
    reason="PySide6 not available in test environment",
)


def test_safe_drop_shadow_renders_offscreen(
    monkeypatch: pytest.MonkeyPatch, qtbot: pytest.QtBot, qapp: QApplication
) -> None:
    monkeypatch.setattr(painter_guard_module, "painter_guard_enabled", True)
    widget = QWidget()
    widget.resize(160, 120)
    widget.setGraphicsEffect(SafeDropShadowEffect("test_shadow", widget))
    widget.setAutoFillBackground(True)

    image = QImage(QSize(160, 120), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.white)

    with painter_on_image(image) as painter:
        assert assert_painter_active(
            painter, "test_safe_drop_shadow_renders_offscreen", strict=True
        )
        widget.render(painter, QPoint(0, 0))

    assert_image_has_content(image)


def test_safe_opacity_renders_offscreen(
    monkeypatch: pytest.MonkeyPatch, qtbot: pytest.QtBot, qapp: QApplication
) -> None:
    monkeypatch.setattr(painter_guard_module, "painter_guard_enabled", True)
    widget = QWidget()
    widget.resize(140, 90)
    widget.setAutoFillBackground(True)

    label = QLabel("fade", widget)
    label.resize(80, 40)
    label.setGraphicsEffect(SafeOpacityEffect("test_opacity", label))

    image = QImage(QSize(140, 90), QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.white)

    with painter_on_image(image) as painter:
        assert assert_painter_active(painter, "test_safe_opacity_renders_offscreen", strict=True)
        widget.render(painter, QPoint(0, 0))

    assert_image_has_content(image)
