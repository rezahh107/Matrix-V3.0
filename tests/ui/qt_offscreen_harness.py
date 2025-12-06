from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QWidget


@contextmanager
def painter_on_image(image: QImage) -> Iterator[QPainter]:
    painter = QPainter(image)
    try:
        if not painter.isActive():
            raise RuntimeError("QPainter failed to activate on QImage")
        yield painter
    finally:
        if painter.isActive():
            painter.end()


def render_widget_offscreen(
    qtbot: Any,
    widget: QWidget,
    size: QSize,
    *,
    fill: int = Qt.transparent,
) -> QImage:
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    widget.resize(size)
    qtbot.addWidget(widget)
    widget.ensurePolished()
    widget.update()
    qtbot.wait(0)

    image = QImage(size, QImage.Format_ARGB32_Premultiplied)
    image.fill(fill)

    with painter_on_image(image) as painter:
        widget.render(painter)

    return image


def assert_image_has_content(image: QImage) -> None:
    ptr = image.constBits()
    ptr.setsize(image.sizeInBytes())
    if not any(ptr):
        pytest.fail("Rendered image is empty (all pixels transparent or zero)")
