import os
from datetime import datetime

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    import PySide6  # noqa: F401
except ImportError as exc:
    pytest.skip(f"PySide6 unavailable: {exc}", allow_module_level=True)

from app.infra.local_database import DatabaseHealthStatus, DatabaseHealthSummary

try:
    from app.ui.theme import build_stylesheet, build_theme
except ImportError as exc:
    pytest.skip(f"Theme unavailable: {exc}", allow_module_level=True)
from app.ui.widgets import DatabaseStatusWidget


@pytest.fixture
def status_widget(qtbot):
    widget = DatabaseStatusWidget(build_theme("light"))
    qtbot.addWidget(widget)
    return widget


def _assert_semantic_status(status_widget, expected_state: str, message: str) -> None:
    assert status_widget._icon_label.text() == "●"
    assert status_widget._icon_label.property("databaseHealth") == expected_state
    assert status_widget._text_label.property("databaseHealth") == expected_state
    assert status_widget._icon_label.styleSheet() == ""
    assert status_widget._text_label.styleSheet() == ""
    assert status_widget._text_label.text() == message
    assert status_widget.accessibleDescription() == f"Database health: {message}"


def test_status_widget_ok_state(status_widget):
    summary = DatabaseHealthSummary(
        status=DatabaseHealthStatus.OK,
        message="پایگاه‌داده: آماده",
        counts={"دانش‌آموز": 5, "پشتیبان": 2},
        last_updated=datetime(2024, 1, 1, 0, 0, 0),
    )

    status_widget.set_summary(summary)

    _assert_semantic_status(status_widget, "ok", summary.message)
    assert "دانش‌آموز: 5" in status_widget.toolTip()
    assert "پشتیبان: 2" in status_widget.toolTip()
    assert "2024-01-01T00:00:00" in status_widget.toolTip()


def test_status_widget_unavailable_state(status_widget):
    summary = DatabaseHealthSummary(
        status=DatabaseHealthStatus.UNAVAILABLE,
        message="پایگاه‌داده: در دسترس نیست",
        counts={},
        last_updated=None,
    )

    status_widget.set_summary(summary)

    _assert_semantic_status(status_widget, "error", summary.message)
    assert status_widget.toolTip() == summary.message


def test_status_widget_degraded_state(status_widget):
    summary = DatabaseHealthSummary(
        status=DatabaseHealthStatus.DEGRADED,
        message="پایگاه‌داده: نیاز به بررسی",
        counts={},
        last_updated=None,
    )

    status_widget.set_summary(summary)

    _assert_semantic_status(status_widget, "warning", summary.message)
    assert status_widget.toolTip() == summary.message


@pytest.mark.parametrize(
    ("semantic_state", "theme_color_role"),
    [
        ("ok", "success"),
        ("warning", "warning"),
        ("error", "error"),
    ],
)
def test_status_widget_semantic_states_are_bound_by_global_stylesheet(
    semantic_state: str,
    theme_color_role: str,
) -> None:
    theme = build_theme("light")
    stylesheet = build_stylesheet(theme)
    selector = f'QLabel[databaseHealth="{semantic_state}"]'
    matching_rule = next(
        (line for line in stylesheet.splitlines() if line.startswith(selector)),
        None,
    )

    assert matching_rule is not None
    assert getattr(theme.colors, theme_color_role) in matching_rule
