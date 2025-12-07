"""Placeholder debug dashboard widget (feature retired).

This widget intentionally does not implement clipboard or file export
behaviour. It exists only to keep imports stable after the removal of the
legacy debug story dashboard.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DebugDashboardWidget(QWidget):
    """Minimal stub widget for the retired debug dashboard."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        label = QLabel("Debug dashboard is disabled in this version.", self)
        label.setWordWrap(True)
        layout.addWidget(label)

    def set_stories(self, stories: Iterable[Any] | None = None) -> None:  # noqa: ARG002
        """Accept debug stories but intentionally ignore them."""

    def get_current_story_text(self) -> str | None:
        """Return no debug story text; feature removed."""

        return None

    def _copy_current_story(self) -> str | None:
        """Legacy shim retained for compatibility; returns no text."""

        return self.get_current_story_text()
