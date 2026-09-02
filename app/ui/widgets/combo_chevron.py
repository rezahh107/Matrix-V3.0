"""Deterministic vector chevron overlay for Matrix-styled QComboBox controls."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, Qt
from PySide6.QtGui import QPainter, QPalette, QPen
from PySide6.QtWidgets import QComboBox, QStyle, QStyleOptionComboBox, QWidget


class _ComboChevronOverlay(QWidget):
    def __init__(self, combo: QComboBox) -> None:
        super().__init__(combo)
        self._combo = combo
        self.setObjectName("comboChevronOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        combo.installEventFilter(self)
        self._sync_geometry()
        self.show()
        self.raise_()

    def _sync_geometry(self) -> None:
        option = QStyleOptionComboBox()
        self._combo.initStyleOption(option)
        rect = self._combo.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self._combo,
        )
        if not rect.isValid() or rect.width() < 8 or rect.height() < 6:
            width = 28
            if self._combo.layoutDirection() == Qt.LayoutDirection.RightToLeft:
                rect = self._combo.rect().adjusted(0, 0, -(self._combo.width() - width), 0)
            else:
                rect = self._combo.rect().adjusted(self._combo.width() - width, 0, 0, 0)
        self.setGeometry(rect)
        self.raise_()
        self.update()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._combo and event.type() in {
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.Show,
            QEvent.Type.LayoutDirectionChange,
            QEvent.Type.StyleChange,
            QEvent.Type.PaletteChange,
            QEvent.Type.EnabledChange,
        }:
            self._sync_geometry()
        return False

    def paintEvent(self, _event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        group = QPalette.ColorGroup.Normal if self._combo.isEnabled() else QPalette.ColorGroup.Disabled
        color = self._combo.palette().color(group, QPalette.ColorRole.Text)
        pen = QPen(color)
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        cx = self.rect().center().x()
        cy = self.rect().center().y()
        painter.drawLine(QPointF(cx - 4.0, cy - 2.0), QPointF(cx, cy + 2.0))
        painter.drawLine(QPointF(cx, cy + 2.0), QPointF(cx + 4.0, cy - 2.0))


def install_combo_chevrons(root: QWidget) -> None:
    """Attach one crisp vector chevron to each combo below ``root``."""

    combos: list[QComboBox] = []
    if isinstance(root, QComboBox):
        combos.append(root)
    combos.extend(root.findChildren(QComboBox))
    for combo in combos:
        existing = combo.findChild(_ComboChevronOverlay, "comboChevronOverlay")
        if existing is None:
            _ComboChevronOverlay(combo)
