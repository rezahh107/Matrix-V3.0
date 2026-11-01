"""Regression checks for database health presentation and semantic styling."""

from datetime import datetime

import pytest

from app.infra.local_database import (
    DatabaseHealthReason,
    DatabaseHealthStatus,
    DatabaseHealthSummary,
)
from app.ui.i18n import Language
from app.ui.texts import UiTranslator
from app.ui.theme import build_stylesheet, build_theme
from app.ui.widgets import DatabaseStatusWidget


@pytest.fixture
def status_widget(qtbot):
    widget = DatabaseStatusWidget(build_theme("light"), translator=UiTranslator(Language.FA))
    qtbot.addWidget(widget)
    return widget


def _assert_semantic_status(widget, expected_state: str, message: str) -> None:
    assert widget._icon_label.text() == "●"
    assert widget._icon_label.property("databaseHealth") == expected_state
    assert widget._text_label.property("databaseHealth") == expected_state
    assert widget._icon_label.styleSheet() == ""
    assert widget._text_label.styleSheet() == ""
    assert widget._text_label.text() == message
    assert widget.accessibleDescription() == message


def test_status_widget_ok_state(status_widget):
    summary = DatabaseHealthSummary(
        status=DatabaseHealthStatus.OK,
        message="پایگاه‌داده: آماده",
        counts={"دانش‌آموز": 5, "پشتیبان": 2},
        last_updated=datetime(2024, 1, 1, 0, 0, 0),
        reason=DatabaseHealthReason.READY,
    )
    status_widget.set_summary(summary)
    _assert_semantic_status(status_widget, "ok", "پایگاه‌داده: آماده")
    assert "دانش‌آموز: 5" in status_widget.toolTip()
    assert "پشتیبان: 2" in status_widget.toolTip()
    assert "آخرین بررسی: 2024-01-01T00:00:00" in status_widget.toolTip()


def test_status_widget_unavailable_state(status_widget):
    summary = DatabaseHealthSummary(
        status=DatabaseHealthStatus.UNAVAILABLE,
        message="پایگاه‌داده: در دسترس نیست",
        counts={},
        reason=DatabaseHealthReason.MISSING_FILE,
    )
    status_widget.set_summary(summary)
    _assert_semantic_status(status_widget, "error", "پایگاه‌داده: فایل یافت نشد")
    assert status_widget.toolTip() == "پایگاه‌داده: فایل یافت نشد"


def test_status_widget_degraded_state(status_widget):
    summary = DatabaseHealthSummary(
        status=DatabaseHealthStatus.DEGRADED,
        message="پایگاه‌داده: نیاز به بررسی",
        counts={},
        reason=DatabaseHealthReason.NEEDS_REVIEW,
    )
    status_widget.set_summary(summary)
    _assert_semantic_status(status_widget, "warning", "پایگاه‌داده: نیاز به بررسی")


@pytest.mark.parametrize(
    ("semantic_state", "theme_color_role"),
    [("ok", "success"), ("warning", "warning"), ("error", "error")],
)
def test_status_widget_semantic_states_are_bound_by_global_stylesheet(
    semantic_state: str, theme_color_role: str
) -> None:
    theme = build_theme("light")
    stylesheet = build_stylesheet(theme)
    selector = f'QLabel[databaseHealth="{semantic_state}"]'
    matching_rule = next(
        (line for line in stylesheet.splitlines() if line.startswith(selector)), None
    )
    assert matching_rule is not None
    assert getattr(theme.colors, theme_color_role) in matching_rule
