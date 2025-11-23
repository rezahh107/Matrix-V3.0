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
    from app.ui.theme import build_theme
except ImportError as exc:
    pytest.skip(f"Theme unavailable: {exc}", allow_module_level=True)
from app.ui.widgets.status_bar import DatabaseStatusWidget


@pytest.fixture
def status_widget(qtbot):
    widget = DatabaseStatusWidget(build_theme("light"))
    qtbot.addWidget(widget)
    return widget


def test_status_widget_ok_state(status_widget):
    summary = DatabaseHealthSummary(
        status=DatabaseHealthStatus.OK,
        message="پایگاه‌داده: آماده",
        counts={"دانش‌آموز": 5, "پشتیبان": 2},
        last_updated=datetime(2024, 1, 1, 0, 0, 0),
    )

    status_widget.set_summary(summary)

    assert status_widget._icon_label.text() == "●"
    assert "#2ecc71" in status_widget._icon_label.styleSheet()
    assert "دانش‌آموز: 5" in status_widget.toolTip()
    assert "2024-01-01T00:00:00" in status_widget.toolTip()
    assert status_widget._text_label.text() == summary.message


def test_status_widget_unavailable_state(status_widget):
    summary = DatabaseHealthSummary(
        status=DatabaseHealthStatus.UNAVAILABLE,
        message="پایگاه‌داده: در دسترس نیست",
        counts={},
        last_updated=None,
    )

    status_widget.set_summary(summary)

    assert "#e74c3c" in status_widget._icon_label.styleSheet()
    assert status_widget.toolTip() == summary.message


def test_status_widget_degraded_state(status_widget):
    summary = DatabaseHealthSummary(
        status=DatabaseHealthStatus.DEGRADED,
        message="پایگاه‌داده: نیاز به بررسی",
        counts={},
        last_updated=None,
    )

    status_widget.set_summary(summary)

    assert "#f1c40f" in status_widget._icon_label.styleSheet()
    assert status_widget._text_label.text() == summary.message
