import pytest

pytest.importorskip(
    "PySide6.QtWidgets",
    reason="PySide6 not available in test environment",
    exc_type=ImportError,
)
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


def test_current_story_text_contains_rule_id(qapp: QApplication) -> None:
    widget = DebugDashboardWidget()
    widget.set_stories([_sample_story()])

    text = widget.get_current_story_text()

    assert isinstance(text, str)
    assert text
    assert "QA_RULE_MENTOR_TYPE_01" in text
