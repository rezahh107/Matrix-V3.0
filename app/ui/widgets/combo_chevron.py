"""Deterministic vector chevron overlay for Matrix-styled QComboBox controls.

`QComboBox` is `STYLED` in `docs/UI_PRESENTATION_AUTHORITY.md`: Matrix owns the
outer shell, the drop-down surface and the arrow pixels while Qt keeps model/view,
popup lifecycle, input and accessibility behavior. The overlay therefore derives
its rectangle from the same `Theme.combo_dropdown_width` token that renders the
QSS `QComboBox::drop-down` surface, instead of asking the active `QStyle` for its
own arrow sub-control rectangle. One token means the Python overlay and the
central QSS cannot drift apart, and the overlay can never fall outside the
Matrix-owned shell at any supported DPI scale.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, QRect, Qt
from PySide6.QtGui import QPainter, QPalette, QPen
from PySide6.QtWidgets import QComboBox, QWidget

from app.ui.theme import Theme

_DROP_DOWN_WIDTH = Theme().combo_dropdown_width
_TRACKED_EVENTS = frozenset(
    {
        QEvent.Type.Resize,
        QEvent.Type.Move,
        QEvent.Type.Show,
        QEvent.Type.LayoutDirectionChange,
        QEvent.Type.StyleChange,
        QEvent.Type.PaletteChange,
        QEvent.Type.EnabledChange,
    }
)


class _ComboChevronOverlay(QWidget):
    def __init__(self, combo: QComboBox) -> None:
        super().__init__(combo)
        self.setObjectName("comboChevronOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        combo.installEventFilter(self)
        self._sync_geometry()
        self.show()
        self.raise_()

    def _combo(self) -> QComboBox | None:
        """Resolve the owning combo from the widget tree.

        The parent relationship is the authority rather than a captured Python
        attribute: Qt owns this overlay, so its Python wrapper may be collected
        and re-created without ``__init__`` ever running again.
        """

        parent = self.parentWidget()
        return parent if isinstance(parent, QComboBox) else None

    def _drop_down_rect(self, combo: QComboBox) -> QRect:
        """Return the Matrix-owned drop-down region in combo coordinates."""

        shell = combo.rect()
        width = max(1, min(_DROP_DOWN_WIDTH, shell.width()))
        leading = combo.layoutDirection() == Qt.LayoutDirection.RightToLeft
        left = shell.left() if leading else shell.right() - width + 1
        return QRect(left, shell.top(), width, shell.height())

    def _sync_geometry(self) -> None:
        combo = self._combo()
        if combo is None:
            return
        self.setGeometry(self._drop_down_rect(combo))
        self.raise_()
        self.update()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._combo() and event.type() in _TRACKED_EVENTS:
            self._sync_geometry()
        return False

    def paintEvent(self, _event) -> None:  # noqa: N802
        combo = self._combo()
        if combo is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        group = QPalette.ColorGroup.Normal if combo.isEnabled() else QPalette.ColorGroup.Disabled
        color = combo.palette().color(group, QPalette.ColorRole.Text)
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
