from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from app.infra.health import HealthSummary, IssueSummary
from app.ui.widgets.health_indicator import HealthCallbacks, HealthIndicatorWidget


def test_health_indicator_updates_and_exports(qtbot, monkeypatch) -> None:
    summary = HealthSummary(
        status="WARN",
        summary_text="System health: WARNING 🟡 (review warnings before using output)",
        counts={"P0": 0, "P1": 1, "P2": 0},
        issues_summary=[IssueSummary(issue_code="QA_RULE_SAMPLE", severity="P1", count=1)],
    )
    exported: list[str] = []

    def _export() -> str:
        exported.append("ok")
        return "/tmp/report.json"

    widget = HealthIndicatorWidget(
        HealthCallbacks(fetch_summary=lambda: summary, export_report=_export)
    )
    qtbot.addWidget(widget)

    captured: list[str] = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: captured.append("info"))
    widget.refresh()
    assert widget._status_label.text() == summary.summary_text

    qtbot.mouseClick(widget._btn_export, Qt.MouseButton.LeftButton)
    assert exported
    assert captured
