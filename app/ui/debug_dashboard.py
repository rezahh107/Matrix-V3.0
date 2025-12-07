"""پنل سادهٔ اشکال‌زدایی QA برای نمایش داستان‌های منتور."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.infra.debug import QADebugStory
from app.infra.debug.qa_debug_presenter import format_story_for_text, summarize_story


class DebugDashboardWidget(QWidget):
    """نمایش‌گر داستان‌های QA با امکان کپی و ذخیره."""

    def __init__(
        self,
        formatter: Callable[[QADebugStory], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._stories: list[QADebugStory] = []
        self._formatter = formatter or format_story_for_text

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self._story_list = QListWidget(splitter)
        self._story_list.setObjectName("listDebugStories")
        self._story_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._story_list.currentItemChanged.connect(self._on_selection_changed)

        detail_pane = QWidget(splitter)
        detail_layout = QVBoxLayout(detail_pane)
        detail_layout.setContentsMargins(8, 0, 0, 0)
        detail_layout.setSpacing(6)

        info_layout = QFormLayout()
        info_layout.setSpacing(4)
        self._rule_label = QLabel("—")
        self._severity_label = QLabel("—")
        self._law_label = QLabel("—")
        info_layout.addRow("Rule", self._rule_label)
        info_layout.addRow("Severity", self._severity_label)
        info_layout.addRow("LAW", self._law_label)
        detail_layout.addLayout(info_layout)

        self._story_view = QPlainTextEdit()
        self._story_view.setObjectName("textDebugStory")
        self._story_view.setReadOnly(True)
        self._story_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        detail_layout.addWidget(self._story_view, 1)

        action_row = QHBoxLayout()
        action_row.setSpacing(8)
        action_row.addStretch(1)
        self._btn_copy = QPushButton("Copy story")
        self._btn_copy.setObjectName("btnCopyDebugStory")
        self._btn_copy.clicked.connect(self._copy_current_story)
        self._btn_save = QPushButton("Save story…")
        self._btn_save.setObjectName("btnSaveDebugStory")
        self._btn_save.clicked.connect(self._save_current_story)
        action_row.addWidget(self._btn_copy)
        action_row.addWidget(self._btn_save)
        detail_layout.addLayout(action_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(splitter)

    def set_stories(self, stories: Sequence[QADebugStory]) -> None:
        """نمایش فهرست تازه‌ای از داستان‌ها."""

        self._stories = list(stories)
        self._story_list.clear()
        for index, story in enumerate(self._stories):
            summary = summarize_story(story)
            item = QListWidgetItem(self._elide_text(summary, max_chars=120))
            item.setData(Qt.ItemDataRole.UserRole, index)
            self._story_list.addItem(item)
        if self._stories:
            self._story_list.setCurrentRow(0)
            self._render_story(self._stories[0])
        else:
            self._render_story(None)

    def _on_selection_changed(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:  # noqa: ARG002 - previous kept for Qt signature
        index = -1 if current is None else int(current.data(Qt.ItemDataRole.UserRole) or -1)
        story = self._stories[index] if 0 <= index < len(self._stories) else None
        self._render_story(story)

    def _render_story(self, story: QADebugStory | None) -> None:
        if story is None:
            self._story_view.setPlainText("هیچ داستانی برای نمایش نیست.")
            self._rule_label.setText("—")
            self._severity_label.setText("—")
            self._law_label.setText("—")
            return

        self._rule_label.setText(str(story.rule_id))
        self._severity_label.setText(story.severity)
        self._law_label.setText(", ".join(story.law_refs) if story.law_refs else "—")
        self._story_view.setPlainText(self._formatter(story))

    def _current_story(self) -> QADebugStory | None:
        item = self._story_list.currentItem()
        if item is None:
            return self._stories[0] if self._stories else None

        index = int(item.data(Qt.ItemDataRole.UserRole) or -1)
        return self._stories[index] if 0 <= index < len(self._stories) else None

    def _current_story_text(self) -> str:
        story = self._current_story()
        if story is None:
            return ""
        return self._formatter(story)

    def _copy_current_story(self) -> None:
        text = self._current_story_text()
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return

        payload = text or ""
        mime = QMimeData()
        mime.setText(payload)

        clipboard.clear(QClipboard.Mode.Clipboard)
        clipboard.setMimeData(mime, mode=QClipboard.Mode.Clipboard)
        clipboard.setText(payload, QClipboard.Mode.Clipboard)
        QApplication.processEvents()

        if payload and payload not in clipboard.text(QClipboard.Mode.Clipboard):
            clipboard.setText(payload, QClipboard.Mode.Clipboard)
            QApplication.processEvents()

    def _save_current_story(self) -> None:
        story = self._current_story()
        if story is None:
            return
        text = self._formatter(story)
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save debug story",
            "qa_debug_story.md",
            "Markdown (*.md);;Text Files (*.txt);;All Files (*)",
        )
        if filename:
            with open(filename, "w", encoding="utf-8") as handle:
                handle.write(text)

    @staticmethod
    def _elide_text(value: str, *, max_chars: int) -> str:
        if len(value) <= max_chars:
            return value
        return value[: max(0, max_chars - 1)] + "…"
