import pytest

try:
    from PySide6.QtWidgets import QApplication
except ImportError:
    pytest.skip("PySide6 not available in test environment", allow_module_level=True)

from app.ui.debug_dashboard import DebugDashboardWidget


@pytest.fixture
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_debug_dashboard_placeholder(qapp: QApplication) -> None:
    widget = DebugDashboardWidget()

    widget.set_stories(["story1", "story2"])

    assert widget.get_current_story_text() is None
