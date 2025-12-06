from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pytest
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication, QWidget


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


def render_widget_offscreen(factory: Callable[[], QWidget]) -> QImage:
    """Synchronously render a widget into an offscreen image.

    Assumes a QApplication already exists (provided by the test harness). The
    widget is created via `factory`, resized to a reasonable size, and rendered
    into a transparent QImage without nested event loops or threading.
    """

    widget = factory()

    size = widget.sizeHint()
    if not size.isValid() or size.isEmpty():
        size = QSize(400, 300)
    widget.resize(size)

    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    QApplication.processEvents()

    image = QImage(size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)

    painter = QPainter(image)
    try:
        widget.render(painter, QPoint(0, 0))
    finally:
        painter.end()

    return image


def assert_image_has_content(image: QImage) -> None:
    ptr = image.constBits()
    ptr.setsize(image.sizeInBytes())
    if not any(ptr):
        pytest.fail("Rendered image is empty (all pixels transparent or zero)")
