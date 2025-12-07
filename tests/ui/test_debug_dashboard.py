import pytest

pytest.importorskip(
    "PySide6.QtWidgets",
    reason="PySide6 not available in test environment",
    exc_type=ImportError,
)
from PySide6.QtGui import QClipboard
from PySide6.QtWidgets import QApplication

from app.core.qa.rules import QA_RULE_MENTOR_TYPE_01
from app.infra.debug.qa_debug_engine import QADebugStory
from app.ui.debug_dashboard import DebugDashboardWidget


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _sample_story() -> QADebugStory:
    return QADebugStory(
        rule_id=QA_RULE_MENTOR_TYPE_01,
        law_refs=("LAW-01",),
        severity="error",
        evidence="alias mismatch",
        context={"matrix_rows": 2},
        story=(
            "🔴 QA_RULE_MENTOR_TYPE_01 / LAW-01",
            "چه شد: نمونه خطا",
            "از کجا/مسیر: تست",
            "چرا: توضیح",
            "گام بعدی: اقدام بعدی",
        ),
    )


def test_set_stories_populates_and_selects_first(qapp: QApplication) -> None:
    widget = DebugDashboardWidget()
    widget.set_stories([_sample_story()])

    assert widget.findChild(type(widget._story_list)) is widget._story_list
    assert widget._story_list.count() == 1
    assert widget._story_list.currentRow() == 0
    assert "QA_RULE_MENTOR_TYPE_01" in widget._story_view.toPlainText()


def test_copy_and_save_actions(
    monkeypatch: pytest.MonkeyPatch, qapp: QApplication, tmp_path
) -> None:
    class _FakeClipboard:
        def __init__(self) -> None:
            self._text = ""

        def clear(  # noqa: N802 - Qt-style name for compatibility
            self, mode: QClipboard.Mode = QClipboard.Mode.Clipboard
        ) -> None:
            self._text = ""

        def setText(  # noqa: N802 - Qt-style name for compatibility
            self, text: str, mode: QClipboard.Mode = QClipboard.Mode.Clipboard
        ) -> None:
            self._text = text

        def text(self) -> str:
            return self._text

    fake_clipboard = _FakeClipboard()
    monkeypatch.setattr(QApplication, "clipboard", lambda: fake_clipboard)

    widget = DebugDashboardWidget()
    widget.set_stories([_sample_story()])

    # Copy
    copied = widget._copy_current_story()
    assert copied is not None
    assert "QA_RULE_MENTOR_TYPE_01" in copied
    assert "QA_RULE_MENTOR_TYPE_01" in fake_clipboard.text()

    # Save
    target = tmp_path / "story.md"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *_, **__: (str(target), "Markdown (*.md)"),
    )
    widget._save_current_story()
    assert target.exists()
    assert "گام بعدی" in target.read_text(encoding="utf-8")
